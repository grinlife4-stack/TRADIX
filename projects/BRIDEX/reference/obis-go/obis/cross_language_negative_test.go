package obis

import (
	"bytes"
	"encoding/json"
	"io"
	"net/http"
	"os"
	"strconv"
	"testing"
	"time"
)

// TestGoRawNegativeRequestsToPythonPeer is activated by the Python integration
// harness while its independent reference server is running. It deliberately
// bypasses Invoke's valid-request constructor so the Go implementation can
// exercise malformed-but-authenticated and unauthenticated wire requests.
func TestGoRawNegativeRequestsToPythonPeer(t *testing.T) {
	endpoint := os.Getenv("OBIS_PYTHON_PEER_ENDPOINT")
	if endpoint == "" {
		t.Skip("OBIS_PYTHON_PEER_ENDPOINT is set only by the cross-language harness")
	}
	secret := []byte("0123456789abcdef0123456789abcdef")
	now := time.Now().Unix()
	request := map[string]any{
		"protocol": Protocol,
		"version": Version,
		"message_type": "request",
		"message_id": "go-raw-negative-version",
		"nonce": "go-raw-negative-version-nonce",
		"sender": map[string]any{"peer_id": "peer:go"},
		"recipient": map[string]any{"peer_id": "peer:python"},
		"issued_at": json.Number(strconv.FormatInt(now, 10)),
		"expires_at": json.Number(strconv.FormatInt(now+30, 10)),
		"capability": map[string]any{"id": "records.read", "version": "1.0"},
		"authorization": map[string]any{"principal_ref": "principal:go", "scopes": []any{"records:read"}},
		"payload": map[string]any{"record_id": "negative-cross-peer"},
	}

	postRaw := func(body []byte, signature string) int {
		req, err := http.NewRequest(http.MethodPost, endpoint+MessagePath, bytes.NewReader(body))
		if err != nil { t.Fatalf("build raw request: %v", err) }
		req.Header.Set("Content-Type", "application/obis+json")
		req.Header.Set("X-OBIS-Key-Id", "go-dev-key")
		if signature != "" {
			req.Header.Set("X-OBIS-Signature", signature)
		}
		response, err := (&http.Client{Timeout: 3 * time.Second}).Do(req)
		if err != nil { t.Fatalf("send raw request: %v", err) }
		defer response.Body.Close()
		return response.StatusCode
	}
	post := func(message map[string]any, signature string) int {
		body, err := CanonicalJSON(message)
		if err != nil { t.Fatalf("canonicalize raw request: %v", err) }
		return postRaw(body, signature)
	}

	unsupported := make(map[string]any, len(request))
	for key, value := range request { unsupported[key] = value }
	unsupported["version"] = "0.2"
	signature, err := Sign(unsupported, secret)
	if err != nil { t.Fatalf("sign unsupported-version request: %v", err) }
	if status := post(unsupported, signature); status != http.StatusUpgradeRequired {
		t.Fatalf("Python peer status for authenticated unsupported version = %d, want 426", status)
	}

	invalidAuth := make(map[string]any, len(request))
	for key, value := range request { invalidAuth[key] = value }
	if status := post(invalidAuth, "00"); status != http.StatusUnauthorized {
		t.Fatalf("Python peer status for invalid signature = %d, want 401", status)
	}

	expired := make(map[string]any, len(request))
	for key, value := range request { expired[key] = value }
	expired["issued_at"] = json.Number(strconv.FormatInt(now-60, 10))
	expired["expires_at"] = json.Number(strconv.FormatInt(now-30, 10))
	expiredSignature, err := Sign(expired, secret)
	if err != nil { t.Fatalf("sign expired request: %v", err) }
	if status := post(expired, expiredSignature); status != http.StatusRequestTimeout {
		t.Fatalf("Python peer status for expired request = %d, want 408", status)
	}

	unknownField := make(map[string]any, len(request)+1)
	for key, value := range request { unknownField[key] = value }
	unknownField["unexpected"] = "not-in-contract"
	unknownSignature, err := Sign(unknownField, secret)
	if err != nil { t.Fatalf("sign unknown-field request: %v", err) }
	if status := post(unknownField, unknownSignature); status != http.StatusBadRequest {
		t.Fatalf("Python peer status for unknown top-level field = %d, want 400", status)
	}

	nestedField := make(map[string]any, len(request))
	for key, value := range request { nestedField[key] = value }
	nestedSender := map[string]any{"peer_id": "peer:go", "bridge_id": "not-in-contract"}
	nestedField["sender"] = nestedSender
	nestedSignature, err := Sign(nestedField, secret)
	if err != nil { t.Fatalf("sign nested-field request: %v", err) }
	if status := post(nestedField, nestedSignature); status != http.StatusBadRequest {
		t.Fatalf("Python peer status for unexpected sender field = %d, want 400", status)
	}

	if status := postRaw([]byte("{"), ""); status != http.StatusBadRequest {
		t.Fatalf("Python peer status for malformed JSON = %d, want 400", status)
	}
	if status := postRaw([]byte("{\"protocol\":\"obis\",\"protocol\":\"obis\"}"), ""); status != http.StatusBadRequest {
		t.Fatalf("Python peer status for duplicate JSON key = %d, want 400", status)
	}
}


// TestGoDurableReplayRequestToPythonPeer sends the same signed request on each
// invocation. The Python integration harness restarts the server between runs
// while retaining its SQLite replay database.
func TestGoDurableReplayRequestToPythonPeer(t *testing.T) {
	endpoint := os.Getenv("OBIS_PYTHON_PEER_ENDPOINT")
	if endpoint == "" {
		t.Skip("OBIS_PYTHON_PEER_ENDPOINT is set only by the cross-language harness")
	}
	expectedStatus, err := strconv.Atoi(os.Getenv("OBIS_EXPECTED_HTTP_STATUS"))
	if err != nil || (expectedStatus != http.StatusOK && expectedStatus != http.StatusConflict) {
		t.Fatalf("OBIS_EXPECTED_HTTP_STATUS must be 200 or 409")
	}

	secret := []byte("0123456789abcdef0123456789abcdef")
	now := time.Now().Unix()
	request := map[string]any{
		"protocol": Protocol,
		"version": Version,
		"message_type": "request",
		"message_id": "go-python-replay-restart-message",
		"nonce": "go-python-replay-restart-nonce",
		"sender": map[string]any{"peer_id": "peer:go"},
		"recipient": map[string]any{"peer_id": "peer:python"},
		"issued_at": json.Number(strconv.FormatInt(now, 10)),
		"expires_at": json.Number(strconv.FormatInt(now+30, 10)),
		"capability": map[string]any{"id": "records.read", "version": "1.0"},
		"authorization": map[string]any{"principal_ref": "principal:go", "scopes": []any{"records:read"}},
		"payload": map[string]any{"record_id": "go-python-replay-restart"},
	}
	body, err := CanonicalJSON(request)
	if err != nil {
		t.Fatalf("canonicalize replay request: %v", err)
	}
	signature, err := Sign(request, secret)
	if err != nil {
		t.Fatalf("sign replay request: %v", err)
	}
	req, err := http.NewRequest(http.MethodPost, endpoint+MessagePath, bytes.NewReader(body))
	if err != nil {
		t.Fatalf("build replay request: %v", err)
	}
	req.Header.Set("Content-Type", "application/obis+json")
	req.Header.Set("X-OBIS-Key-Id", "go-dev-key")
	req.Header.Set("X-OBIS-Signature", signature)
	response, err := (&http.Client{Timeout: 5 * time.Second}).Do(req)
	if err != nil {
		t.Fatalf("send replay request to Python peer: %v", err)
	}
	defer response.Body.Close()

	responseBody, err := io.ReadAll(response.Body)
	if err != nil {
		t.Fatalf("read Python peer response: %v", err)
	}
	var responseMessage map[string]any
	if err := json.Unmarshal(responseBody, &responseMessage); err != nil {
		t.Fatalf("decode Python peer response: %v", err)
	}
	if response.StatusCode != expectedStatus {
		t.Fatalf("Python peer status = %d, want %d; body=%s", response.StatusCode, expectedStatus, responseBody)
	}
	if !Verify(responseMessage, secret, response.Header.Get("X-OBIS-Signature")) {
		t.Fatal("Python peer response signature is missing or invalid")
	}
	if responseMessage["correlation_id"] != request["message_id"] {
		t.Fatalf("response correlation_id = %v, want %v", responseMessage["correlation_id"], request["message_id"])
	}
	if expectedStatus == http.StatusOK {
		if responseMessage["outcome"] != "succeeded" {
			t.Fatalf("first response outcome = %v, want succeeded", responseMessage["outcome"])
		}
	} else {
		if responseMessage["outcome"] != "failed" {
			t.Fatalf("replay response outcome = %v, want failed", responseMessage["outcome"])
		}
		errorObject, ok := responseMessage["error"].(map[string]any)
		if !ok || errorObject["code"] != "request.replay_detected" {
			t.Fatalf("replay response error = %v, want request.replay_detected", responseMessage["error"])
		}
	}
}
