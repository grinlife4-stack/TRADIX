package peer

import (
	"encoding/json"
	"testing"
	"time"
)

func TestCanonicalJSONAndHMACMatchPythonDevelopmentVector(t *testing.T) {
	message := map[string]any{
		"protocol": "obis",
		"version": "0.1",
		"message_type": "request",
		"message_id": "m-1",
		"nonce": "n-1",
		"sender": map[string]any{"peer_id": "python-peer"},
		"recipient": map[string]any{"peer_id": "go-peer"},
		"issued_at": json.Number("1763640000.0"),
		"expires_at": json.Number("1763640060.0"),
		"capability": map[string]any{"id": "catalog.lookup", "version": "1.0"},
		"authorization": map[string]any{"principal_ref": "principal:python", "scopes": []any{"catalog:read"}},
		"payload": map[string]any{"item_id": "sample-1", "text": "hello"},
	}
	canonical, err := CanonicalJSON(message)
	if err != nil {
		t.Fatal(err)
	}
	want := \`{"authorization":{"principal_ref":"principal:python","scopes":["catalog:read"]},"capability":{"id":"catalog.lookup","version":"1.0"},"expires_at":1763640060.0,"issued_at":1763640000.0,"message_id":"m-1","message_type":"request","nonce":"n-1","payload":{"item_id":"sample-1","text":"hello"},"protocol":"obis","recipient":{"peer_id":"go-peer"},"sender":{"peer_id":"python-peer"},"version":"0.1"}\`
	if string(canonical) != want {
		t.Fatalf("canonical mismatch:\n%s", canonical)
	}
	secret := []byte("0123456789abcdef0123456789abcdef")
	signature, err := Sign(message, secret)
	if err != nil {
		t.Fatal(err)
	}
	const expected = "ded7c11c6a158eecf849f881064c83bac3b320ef68e0256ef1293e3a5c9064be"
	if signature != expected || !Verify(message, secret, expected) {
		t.Fatalf("Python HMAC vector mismatch: %s", signature)
	}
}

func TestRequestValidationAndReplayProtection(t *testing.T) {
	secret := []byte("0123456789abcdef0123456789abcdef")
	credential := Credential{
		KeyID: "python-key", PeerID: "python-peer", PrincipalRef: "principal:python",
		Secret: secret, AllowedScopes: map[string]bool{"catalog:read": true},
	}
	server, err := NewPeer("go-peer", credential)
	if err != nil {
		t.Fatal(err)
	}
	if err := server.RegisterCapability("catalog.lookup", "1.0", map[string]bool{"catalog:read": true},
		func(payload map[string]any) (map[string]any, error) { return map[string]any{"ok": true}, nil }); err != nil {
		t.Fatal(err)
	}
	message := map[string]any{
		"protocol": "obis", "version": "0.1", "message_type": "request",
		"message_id": "m-1", "nonce": "n-1",
		"sender": map[string]any{"peer_id": "python-peer"},
		"recipient": map[string]any{"peer_id": "go-peer"},
		"issued_at": json.Number("1763640000"), "expires_at": json.Number("1763640060"),
		"capability": map[string]any{"id": "catalog.lookup", "version": "1.0"},
		"authorization": map[string]any{"principal_ref": "principal:python", "scopes": []any{"catalog:read"}},
		"payload": map[string]any{"item_id": "sample-1"},
	}
	signature, err := Sign(message, secret)
	if err != nil {
		t.Fatal(err)
	}
	now := time.Unix(1763640000, 0)
	if _, _, err := server.validate(message, "python-key", signature, now); err != nil {
		t.Fatalf("valid request rejected: %v", err)
	}
	if _, _, err := server.validate(message, "python-key", signature, now); err == nil || err.Error() != "request.replay_detected" {
		t.Fatalf("expected replay rejection, got %v", err)
	}
}

func TestRejectsUnauthorizedScope(t *testing.T) {
	secret := []byte("0123456789abcdef0123456789abcdef")
	credential := Credential{
		KeyID: "python-key", PeerID: "python-peer", PrincipalRef: "principal:python",
		Secret: secret, AllowedScopes: map[string]bool{"catalog:read": true},
	}
	server, _ := NewPeer("go-peer", credential)
	_ = server.RegisterCapability("catalog.lookup", "1.0", map[string]bool{"catalog:read": true},
		func(payload map[string]any) (map[string]any, error) { return map[string]any{"ok": true}, nil })
	message := map[string]any{
		"protocol": "obis", "version": "0.1", "message_type": "request",
		"message_id": "m-2", "nonce": "n-2",
		"sender": map[string]any{"peer_id": "python-peer"},
		"recipient": map[string]any{"peer_id": "go-peer"},
		"issued_at": json.Number("1763640000"), "expires_at": json.Number("1763640060"),
		"capability": map[string]any{"id": "catalog.lookup", "version": "1.0"},
		"authorization": map[string]any{"principal_ref": "principal:python", "scopes": []any{"catalog:write"}},
		"payload": map[string]any{"item_id": "sample-1"},
	}
	signature, _ := Sign(message, secret)
	if _, _, err := server.validate(message, "python-key", signature, time.Unix(1763640000, 0)); err == nil || err.Error() != "authorization.denied" {
		t.Fatalf("expected authorization denial, got %v", err)
	}
}
