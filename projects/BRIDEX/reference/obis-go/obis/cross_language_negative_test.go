package obis

import (
	"bytes"
	"encoding/json"
	"net/http"
	"os"
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
		"issued_at": json.Number(time.Unix(now, 0).Format("")),
		"expires_at": json.Number(time.Unix(now+30, 0).Format("")),
		"capability": map[string]any{"id": "records.read", "version": "1.0"},
		"authorization": map[string]any{"principal_ref": "principal:go", "scopes": []any{"records:read"}},
		"payload": map[string]any{"record_id": "negative-cross-peer"},
	}
	// Use integer JSON numbers, not floating-point timestamps.
	request["issued_at"] = json.Number(strconv.FormatInt(now, 10))
	request["expires_at"] = json.Number(strconv.FormatInt(now+30, 10))

	post := func(message map[string]any, signature string) int {
		body, err := CanonicalJSON(message)
		if err != nil { t.Fatalf("canonicalize raw request: %v", err) }
		req, err := http.NewRequest(http.MethodPost, endpoint+MessagePath, bytes.NewReader(body))
		if err != nil { t.Fatalf("build raw request: %v", err) }
		req.Header.Set("Content-Type", "application/obis+json")
		req.Header.Set("X-OBIS-Key-Id", "go-dev-key")
		req.Header.Set("X-OBIS-Signature", signature)
		response, err := (&http.Client{Timeout: 3 * time.Second}).Do(req)
		if err != nil { t.Fatalf("send raw request: %v", err) }
		defer response.Body.Close()
		return response.StatusCode
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
}
