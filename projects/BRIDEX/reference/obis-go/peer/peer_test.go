package peer

import (
	"encoding/json"
	"net/url"
	"strings"
	"testing"
	"crypto/x509"
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
	want := `{"authorization":{"principal_ref":"principal:python","scopes":["catalog:read"]},"capability":{"id":"catalog.lookup","version":"1.0"},"expires_at":1763640060.0,"issued_at":1763640000.0,"message_id":"m-1","message_type":"request","nonce":"n-1","payload":{"item_id":"sample-1","text":"hello"},"protocol":"obis","recipient":{"peer_id":"go-peer"},"sender":{"peer_id":"python-peer"},"version":"0.1"}`
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
	if _, _, err := server.validate(message, "python-key", signature, "", "", now); err != nil {
		t.Fatalf("valid request rejected: %v", err)
	}
	if _, _, err := server.validate(message, "python-key", signature, "", "", now); err == nil || err.Error() != "request.replay_detected" {
		t.Fatalf("expected replay rejection, got %v", err)
	}
	if !server.RevokeCredential("python-key") {
		t.Fatal("credential revocation did not take effect")
	}
	message["message_id"] = "m-after-revoke"
	message["nonce"] = "n-after-revoke"
	signature, err = Sign(message, secret)
	if err != nil {
		t.Fatal(err)
	}
	if _, _, err := server.validate(message, "python-key", signature, "", "", now); err == nil || err.Error() != "identity.credential_revoked" {
		t.Fatalf("expected revoked credential rejection, got %v", err)
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
	if _, _, err := server.validate(message, "python-key", signature, "", "", time.Unix(1763640000, 0)); err == nil || err.Error() != "authorization.denied" {
		t.Fatalf("expected authorization denial, got %v", err)
	}
}


func TestNewPeerAcceptsCertificateBoundCredentialWithoutHMAC(t *testing.T) {
	peerURI := "urn:obis:peer:11111111-1111-4111-8111-111111111111"
	credential := Credential{
		KeyID: "client-cert",
		PeerID: peerURI,
		PrincipalRef: "principal:client",
		CertificateURI: peerURI,
		CertificateSHA256: strings.Repeat("a", 64),
		AllowedScopes: map[string]bool{"catalog:read": true},
	}
	if _, err := NewPeer("urn:obis:peer:22222222-2222-4222-8222-222222222222", credential); err != nil {
		t.Fatalf("valid mTLS credential rejected: %v", err)
	}
}

func TestNewPeerRejectsMismatchedOrSecretBearingMTLSCredential(t *testing.T) {
	peerURI := "urn:obis:peer:11111111-1111-4111-8111-111111111111"
	base := Credential{
		KeyID: "client-cert",
		PeerID: peerURI,
		PrincipalRef: "principal:client",
		CertificateURI: peerURI,
		CertificateSHA256: strings.Repeat("a", 64),
		AllowedScopes: map[string]bool{"catalog:read": true},
	}
	mismatched := base
	mismatched.CertificateURI = "urn:obis:peer:33333333-3333-4333-8333-333333333333"
	if _, err := NewPeer("urn:obis:peer:22222222-2222-4222-8222-222222222222", mismatched); err == nil {
		t.Fatal("mismatched certificate URI accepted")
	}
	secretBearing := base
	secretBearing.Secret = []byte("0123456789abcdef0123456789abcdef")
	if _, err := NewPeer("urn:obis:peer:22222222-2222-4222-8222-222222222222", secretBearing); err == nil {
		t.Fatal("mTLS credential with HMAC secret accepted")
	}
}

func TestPeerIDFromCertificateRequiresOneCanonicalOBISURI(t *testing.T) {
	valid, _ := url.Parse("urn:obis:peer:11111111-1111-4111-8111-111111111111")
	got, err := PeerIDFromCertificate(&x509.Certificate{URIs: []*url.URL{valid}})
	if err != nil || got != valid.String() {
		t.Fatalf("valid OBIS URI SAN rejected: %q %v", got, err)
	}
	invalid, _ := url.Parse("urn:obis:peer:not-a-uuid")
	if _, err := PeerIDFromCertificate(&x509.Certificate{URIs: []*url.URL{invalid}}); err == nil {
		t.Fatal("invalid OBIS URI SAN accepted")
	}
}


func TestRevokeCredentialRejectsUnknownOrRepeatedKey(t *testing.T) {
	credential := Credential{
		KeyID: "key-1", PeerID: "peer-1", PrincipalRef: "principal:one",
		Secret: []byte("0123456789abcdef0123456789abcdef"),
		AllowedScopes: map[string]bool{"catalog:read": true},
	}
	server, err := NewPeer("peer-2", credential)
	if err != nil {
		t.Fatal(err)
	}
	if server.RevokeCredential("unknown") {
		t.Fatal("unknown key was revoked")
	}
	if !server.RevokeCredential("key-1") {
		t.Fatal("configured key was not revoked")
	}
	if server.RevokeCredential("key-1") {
		t.Fatal("repeated revocation must be idempotent and report no new change")
	}
}


func TestMTLSCredentialRevocationBlocksSubsequentRequest(t *testing.T) {
	peerURI := "urn:obis:peer:11111111-1111-4111-8111-111111111111"
	serverURI := "urn:obis:peer:22222222-2222-4222-8222-222222222222"
	fingerprint := strings.Repeat("a", 64)
	server, err := NewPeer(serverURI, Credential{
		KeyID: "client-cert",
		PeerID: peerURI,
		PrincipalRef: "principal:client",
		CertificateURI: peerURI,
		CertificateSHA256: fingerprint,
		AllowedScopes: map[string]bool{"catalog:read": true},
	})
	if err != nil {
		t.Fatal(err)
	}
	if err := server.RegisterCapability("catalog.lookup", "1.0", map[string]bool{"catalog:read": true},
		func(payload map[string]any) (map[string]any, error) { return map[string]any{"ok": true}, nil }); err != nil {
		t.Fatal(err)
	}
	message := map[string]any{
		"protocol": "obis", "version": "0.1", "message_type": "request",
		"message_id": "mtls-m-1", "nonce": "mtls-n-1",
		"sender": map[string]any{"peer_id": peerURI},
		"recipient": map[string]any{"peer_id": serverURI},
		"issued_at": json.Number("1763640000"), "expires_at": json.Number("1763640060"),
		"capability": map[string]any{"id": "catalog.lookup", "version": "1.0"},
		"authorization": map[string]any{"principal_ref": "principal:client", "scopes": []any{"catalog:read"}},
		"payload": map[string]any{"item_id": "sample"},
	}
	now := time.Unix(1763640000, 0)
	if _, _, err := server.validate(message, "client-cert", "", peerURI, fingerprint, now); err != nil {
		t.Fatalf("valid mTLS request rejected: %v", err)
	}
	if !server.RevokeCredential("client-cert") {
		t.Fatal("mTLS credential revocation did not take effect")
	}
	message["message_id"] = "mtls-m-after-revoke"
	message["nonce"] = "mtls-n-after-revoke"
	if _, _, err := server.validate(message, "client-cert", "", peerURI, fingerprint, now); err == nil || err.Error() != "identity.credential_revoked" {
		t.Fatalf("expected revoked mTLS credential rejection, got %v", err)
	}
}
