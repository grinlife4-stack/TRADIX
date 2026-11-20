package obis

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net"
	"net/http"
	"net/url"
	"sort"
	"strconv"
	"strings"
	"time"
)

// Invoke sends one authenticated request to an explicitly configured loopback
// peer using the development-only HMAC profile.
func Invoke(endpoint, localPeerID, remotePeerID, keyID, principalRef string, secret []byte, scopes []string, capabilityID, capabilityVersion string, payload map[string]any) (map[string]any, error) {
	if len(secret) < 32 || localPeerID == "" || remotePeerID == "" || keyID == "" || principalRef == "" || capabilityID == "" || capabilityVersion == "" {
		return nil, fmt.Errorf("peer, principal, capability, key, and 32-byte secret are required")
	}
	parsed, err := url.Parse(endpoint)
	if err != nil || parsed.Scheme != "http" || parsed.User != nil || parsed.RawQuery != "" || parsed.Fragment != "" || (parsed.Path != "" && parsed.Path != "/") {
		return nil, fmt.Errorf("endpoint must be a bare loopback HTTP base URL")
	}
	host, _, err := net.SplitHostPort(parsed.Host)
	if err != nil {
		return nil, fmt.Errorf("endpoint must include a loopback port")
	}
	ip := net.ParseIP(host)
	if host != "localhost" && (ip == nil || !ip.IsLoopback()) {
		return nil, fmt.Errorf("development client is loopback-only")
	}
	if len(scopes) == 0 {
		return nil, fmt.Errorf("explicit scopes are required")
	}
	normalizedScopes := append([]string(nil), scopes...)
	sort.Strings(normalizedScopes)
	for i, scope := range normalizedScopes {
		if scope == "" || (i > 0 && scope == normalizedScopes[i-1]) {
			return nil, fmt.Errorf("scopes must be unique non-empty strings")
		}
	}
	now := time.Now().Unix()
	request := map[string]any{
		"protocol": Protocol,
		"version": Version,
		"message_type": "request",
		"message_id": fmt.Sprintf("go-%d", time.Now().UnixNano()),
		"nonce": fmt.Sprintf("nonce-%d", time.Now().UnixNano()),
		"sender": map[string]any{"peer_id": localPeerID},
		"recipient": map[string]any{"peer_id": remotePeerID},
		"issued_at": now,
		"expires_at": now + MaxTTLSeconds,
		"capability": map[string]any{"id": capabilityID, "version": capabilityVersion},
		"authorization": map[string]any{"principal_ref": principalRef, "scopes": stringSliceToAny(normalizedScopes)},
		"payload": payload,
	}
	body, err := CanonicalJSON(request)
	if err != nil { return nil, err }
	signature, err := Sign(request, secret)
	if err != nil { return nil, err }
	httpRequest, err := http.NewRequestWithContext(context.Background(), http.MethodPost, strings.TrimRight(endpoint, "/")+MessagePath, bytes.NewReader(body))
	if err != nil { return nil, err }
	httpRequest.Header.Set("Content-Type", "application/obis+json")
	httpRequest.Header.Set("X-OBIS-Key-Id", keyID)
	httpRequest.Header.Set("X-OBIS-Signature", signature)
	client := &http.Client{Timeout: 3 * time.Second}
	response, err := client.Do(httpRequest)
	if err != nil { return nil, err }
	defer response.Body.Close()
	responseBody, err := io.ReadAll(io.LimitReader(response.Body, MaxMessageBytes+1))
	if err != nil { return nil, err }
	if len(responseBody) == 0 || len(responseBody) > MaxMessageBytes { return nil, fmt.Errorf("response size is invalid") }
	message, err := DecodeStrict(responseBody)
	if err != nil { return nil, err }
	responseSignature := response.Header.Get("X-OBIS-Signature")
	if responseSignature == "" || !Verify(message, secret, responseSignature) {
		return nil, fmt.Errorf("response authentication failed")
	}
	if message["protocol"] != Protocol || message["version"] != Version || message["message_type"] != "response" {
		return nil, fmt.Errorf("invalid response protocol envelope")
	}
	correlation, ok := str(message, "correlation_id")
	if !ok || correlation != request["message_id"] { return nil, fmt.Errorf("response correlation mismatch") }
	sender, ok1 := obj(message, "sender")
	recipient, ok2 := obj(message, "recipient")
	if !ok1 || !ok2 || !exactKeys(sender, "peer_id") || !exactKeys(recipient, "peer_id") {
		return nil, fmt.Errorf("invalid response peer references")
	}
	senderID, _ := str(sender, "peer_id")
	recipientID, _ := str(recipient, "peer_id")
	if senderID != remotePeerID || recipientID != localPeerID { return nil, fmt.Errorf("response peer identity mismatch") }
	if _, ok := number(message, "issued_at"); !ok { return nil, fmt.Errorf("invalid response timestamp") }
	outcome, ok := str(message, "outcome")
	if !ok { return nil, fmt.Errorf("invalid response outcome") }
	if outcome == "succeeded" {
		if !exactKeys(message, "protocol", "version", "message_type", "message_id", "correlation_id", "sender", "recipient", "issued_at", "outcome", "result") {
			return nil, fmt.Errorf("success response has unknown or missing fields")
		}
		if response.StatusCode != http.StatusOK { return nil, fmt.Errorf("unexpected success HTTP status: %d", response.StatusCode) }
		if _, ok := obj(message, "result"); !ok { return nil, fmt.Errorf("success result must be an object") }
		return message, nil
	}
	if outcome == "failed" {
		if !exactKeys(message, "protocol", "version", "message_type", "message_id", "correlation_id", "sender", "recipient", "issued_at", "outcome", "error") {
			return nil, fmt.Errorf("error response has unknown or missing fields")
		}
		errorObject, ok := obj(message, "error")
		if !ok || !exactKeys(errorObject, "code", "message") { return nil, fmt.Errorf("invalid structured error") }
		code, ok1 := str(errorObject, "code")
		messageText, ok2 := str(errorObject, "message")
		if !ok1 || !ok2 { return nil, fmt.Errorf("invalid structured error fields") }
		return nil, &Error{Code: code, Message: messageText, Status: response.StatusCode}
	}
	return nil, fmt.Errorf("unsupported response outcome")
}

func stringSliceToAny(values []string) []any {
	result := make([]any, len(values))
	for i, value := range values { result[i] = value }
	return result
}

// DecodeJSONPayload parses a JSON object supplied to the CLI.
func DecodeJSONPayload(raw string) (map[string]any, error) {
	if strings.TrimSpace(raw) == "" { return map[string]any{}, nil }
	value, err := DecodeStrict([]byte(raw))
	if err != nil { return nil, err }
	return value, nil
}

var _ = json.Number("")
var _ = strconv.IntSize
