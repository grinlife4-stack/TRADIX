package main

import (
	"encoding/hex"
	"encoding/json"
	"flag"
	"fmt"
	"log"
	"net/http"
	"os"
	"strings"

	"github.com/grinlife4-stack/bridex-obis-go/obis"
)

func main() {
	mode := flag.String("mode", "server", "server or invoke")
	peerID := flag.String("peer-id", "peer:go", "local peer identifier")
	addr := flag.String("listen", "127.0.0.1:0", "loopback listen address")
	endpoint := flag.String("endpoint", "", "bare loopback peer base URL for invoke mode")
	keyID := flag.String("key-id", "go-dev-key", "development credential key id")
	remoteID := flag.String("remote-peer", "peer:python", "remote peer identifier")
	principal := flag.String("principal", "principal:python", "authenticated principal")
	secretHex := flag.String("secret-hex", "", "32-byte development secret in hex")
	scopesRaw := flag.String("scopes", "records:read", "comma-separated granted/requested scopes")
	capabilityID := flag.String("capability", "records.read", "capability identifier for invoke mode")
	capabilityVersion := flag.String("capability-version", "1.0", "capability version for invoke mode")
	payloadJSON := flag.String("payload-json", "{}", "JSON object payload for invoke mode")
	flag.Parse()

	secret, err := hex.DecodeString(strings.TrimSpace(*secretHex))
	if err != nil || len(secret) < 32 {
		log.Fatal("secret-hex must encode at least 32 bytes")
	}
	scopes := []string{}
	scopeSet := map[string]bool{}
	for _, scope := range strings.Split(*scopesRaw, ",") {
		if scope != "" && !scopeSet[scope] {
			scopes = append(scopes, scope)
			scopeSet[scope] = true
		}
	}

	switch *mode {
	case "server":
		peer, err := obis.NewPeer(*peerID)
		if err != nil { log.Fatal(err) }
		if err = peer.AddCredential(obis.Credential{
			KeyID: *keyID, PeerID: *remoteID, PrincipalRef: *principal,
			Secret: secret, AllowedScopes: scopeSet,
		}); err != nil { log.Fatal(err) }
		err = peer.RegisterCapability(obis.Capability{
			ID: "records.read", Version: "1.0",
			RequiredScopes: map[string]bool{"records:read": true},
			Handler: func(payload map[string]any) (map[string]any, error) {
				return map[string]any{"record_id": payload["record_id"], "served_by": "go-peer"}, nil
			},
		})
		if err != nil { log.Fatal(err) }
		listener, err := obis.ListenLoopback(*addr, peer.Handler())
		if err != nil { log.Fatal(err) }
		fmt.Println(listener.Addr().String())
		if err = http.Serve(listener, peer.Handler()); err != nil { log.Fatal(err) }
	case "invoke":
		payload, err := obis.DecodeJSONPayload(*payloadJSON)
		if err != nil { log.Fatal(err) }
		response, err := obis.Invoke(*endpoint, *peerID, *remoteID, *keyID, *principal, secret, scopes, *capabilityID, *capabilityVersion, payload)
		if err != nil { log.Fatal(err) }
		encoder := json.NewEncoder(os.Stdout)
		encoder.SetEscapeHTML(false)
		if err = encoder.Encode(response); err != nil { log.Fatal(err) }
	default:
		log.Fatalf("unsupported mode %q", *mode)
	}
}
