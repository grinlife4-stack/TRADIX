package obis

import (
	"bytes"
	"crypto/rand"
	"encoding/hex"
	"errors"
	"fmt"
	"io"
	"net"
	"net/http"
	"net/url"
	"sort"
	"strings"
	"time"
)

// Invoke sends a request directly to one explicitly configured loopback peer.
// It implements only the local development HMAC binding.
func Invoke(endpoint, localPeerID, remotePeerID, keyID, principal string, secret []byte, scopes []string, capabilityID, capabilityVersion string, payload map[string]any) (map[string]any, error) {
	if localPeerID == "" || remotePeerID == "" || keyID == "" || principal == "" || len(secret) < 32 || len(scopes) == 0 || capabilityID == "" || capabilityVersion == "" || payload == nil {
		return nil, errors.New("peer, principal, key, secret, scopes, capability, and payload are required")
	}
	u, err := url.Parse(endpoint)
	if err != nil { return nil, err }
	ip := net.ParseIP(u.Hostname())
	if u.Scheme != "http" || u.User != nil || u.RawQuery != "" || u.Fragment != "" || (u.Path != "" && u.Path != "/") || (u.Hostname() != "localhost" && (ip == nil || !ip.IsLoopback())) {
		return nil, errors.New("development client accepts only a bare loopback HTTP endpoint")
	}
	if _, _, err := net.SplitHostPort(u.Host); err != nil { return nil, errors.New("endpoint must include a port") }

	normalizedScopes := append([]string(nil), scopes...)
	sort.Strings(normalizedScopes)
	for i, scope := range normalizedScopes {
		if scope == "" || (i > 0 && scope == normalizedScopes[i-1]) {
			return nil, errors.New("scopes must be unique non-empty strings")
		}
	}
	messageID := make([]byte, 18)
	nonce := make([]byte, 24)
	if _, err := rand.Read(messageID); err != nil { return nil, err }
	if _, err := rand.Read(nonce); err != nil { return nil, err }
	issued := time.Now().Unix()
	scopeValues := make([]any, len(normalizedScopes))
	for i, scope := range normalizedScopes { scopeValues[i] = scope }
	message := map[string]any{
		"protocol": Protocol, "version": Version, "message_type": "request",
		"message_id": hex.EncodeToString(messageID), "nonce": hex.EncodeToString(nonce),
		"sender": map[string]any{"peer_id": localPeerID},
		"recipient": map[string]any{"peer_id": remotePeerID},
		"issued_at": issued, "expires_at": issued + int64(MaxTTLSeconds),
		"capability": map[string]any{"id": capabilityID, "version": capabilityVersion},
		"authorization": map[string]any{"principal_ref": principal, "scopes": scopeValues},
		"payload": payload,
	}
	body, err := CanonicalJSON(message)
	if err != nil { return nil, err }
	signature, err := Sign(message, secret)
	if err != nil { return nil, err }
	request, err := http.NewRequest(http.MethodPost, strings.TrimRight(endpoint, "/")+MessagePath, bytes.NewReader(body))
	if err != nil { return nil, err }
	request.Header.Set("Content-Type", "application/obis+json")
	request.Header.Set("X-OBIS-Key-Id", keyID)
	request.Header.Set("X-OBIS-Signature", signature)

	client := &http.Client{Timeout: 3 * time.Second}
	response, err := client.Do(request)
	if err != nil { return nil, err }
	defer response.Body.Close()
	responseBody, err := io.ReadAll(io.LimitReader(response.Body, MaxMessageBytes+1))
	if err != nil { return nil, err }
	if len(responseBody) == 0 || len(responseBody) > MaxMessageBytes { return nil, errors.New("response size is invalid") }
	if response.Header.Get("Content-Type") != "application/obis+json" { return nil, errors.New("unexpected response content type") }
	if response.StatusCode != http.StatusOK { return nil, fmt.Errorf("peer returned HTTP %d", response.StatusCode) }
	messageResponse, err := DecodeStrict(responseBody)
	if err != nil { return nil, err }
	if !Verify(messageResponse, secret, response.Header.Get("X-OBIS-Signature")) { return nil, errors.New("response signature verification failed") }
	if err := validateSuccessResponse(messageResponse, message["message_id"].(string), localPeerID, remotePeerID); err != nil { return nil, err }
	return messageResponse, nil
}

func validateSuccessResponse(message map[string]any, requestID, localPeerID, remotePeerID string) error {
	keys := []string{"protocol", "version", "message_type", "message_id", "correlation_id", "sender", "recipient", "issued_at", "outcome", "result"}
	if !exactKeys(message, keys...) { return errors.New("response has unknown or missing fields") }
	if message["protocol"] != Protocol || message["version"] != Version || message["message_type"] != "response" || message["outcome"] != "succeeded" {
		return errors.New("invalid success response envelope")
	}
	messageID, ok1 := str(message, "message_id")
	correlation, ok2 := str(message, "correlation_id")
	if !ok1 || messageID == "" || !ok2 || correlation != requestID { return errors.New("response correlation mismatch") }
	sender, ok1 := obj(message, "sender")
	recipient, ok2 := obj(message, "recipient")
	if !ok1 || !ok2 || !exactKeys(sender, "peer_id") || !exactKeys(recipient, "peer_id") { return errors.New("invalid response peer references") }
	senderID, _ := str(sender, "peer_id")
	recipientID, _ := str(recipient, "peer_id")
	if senderID != remotePeerID || recipientID != localPeerID { return errors.New("response peer identity mismatch") }
	if _, ok := number(message, "issued_at"); !ok { return errors.New("invalid response timestamp") }
	if _, ok := obj(message, "result"); !ok { return errors.New("response result must be an object") }
	return nil
}
