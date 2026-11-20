package peer

import (
	"context"
	"net/http/httptest"
	"testing"
)

func TestGoClientInvokesGoPeerOverHTTPDevelopmentBinding(t *testing.T) {
	secret := []byte("0123456789abcdef0123456789abcdef")
	credential := Credential{
		KeyID: "go-key",
		PeerID: "caller-peer",
		PrincipalRef: "principal:caller",
		Secret: secret,
		AllowedScopes: map[string]bool{"demo:read": true},
	}
	serverPeer, err := NewPeer("target-peer", credential)
	if err != nil {
		t.Fatal(err)
	}
	if err := serverPeer.RegisterCapability(
		"demo.echo", "1.0", map[string]bool{"demo:read": true},
		func(payload map[string]any) (map[string]any, error) {
			return map[string]any{"echo": payload["value"]}, nil
		},
	); err != nil {
		t.Fatal(err)
	}
	server := httptest.NewServer(serverPeer)
	defer server.Close()

	client, err := NewClient(ClientConfig{
		LocalPeerID: "caller-peer",
		RemotePeerID: "target-peer",
		KeyID: "go-key",
		PrincipalRef: "principal:caller",
		Secret: secret,
		Scopes: map[string]bool{"demo:read": true},
		HTTPClient: server.Client(),
	})
	if err != nil {
		t.Fatal(err)
	}
	response, err := client.Invoke(context.Background(), server.URL, "demo.echo", "1.0", map[string]any{"value": "round-trip"})
	if err != nil {
		t.Fatal(err)
	}
	result, ok := response["result"].(map[string]any)
	if !ok || result["echo"] != "round-trip" {
		t.Fatalf("unexpected response result: %#v", response["result"])
	}
}
