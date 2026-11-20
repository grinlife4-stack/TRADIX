package main

import (
	"context"
	"encoding/json"
	"log"
	"net/http"
	"net/url"
	"os"
	"time"

	"example.com/bridex/obis-go/peer"
)

func required(name string) string {
	value := os.Getenv(name)
	if value == "" {
		log.Fatalf("%s is required", name)
	}
	return value
}

func envOr(name, fallback string) string {
	if value := os.Getenv(name); value != "" {
		return value
	}
	return fallback
}

func main() {
	endpoint := required("OBIS_REMOTE_ENDPOINT")
	parsed, err := url.Parse(endpoint)
	if err != nil || parsed.Hostname() == "" {
		log.Fatal("OBIS_REMOTE_ENDPOINT must be a valid peer URL")
	}
	localPeerID := envOr("OBIS_LOCAL_PEER_ID", "go-peer")
	remotePeerID := envOr("OBIS_REMOTE_PEER_ID", "python-peer")
	keyID := envOr("OBIS_KEY_ID", "go-key")
	principal := envOr("OBIS_PRINCIPAL_REF", "principal:go")

	caPath := os.Getenv("OBIS_TLS_CA")
	certPath := os.Getenv("OBIS_TLS_CERT")
	keyPath := os.Getenv("OBIS_TLS_KEY")
	tlsEnabled := caPath != "" || certPath != "" || keyPath != ""
	if tlsEnabled && (caPath == "" || certPath == "" || keyPath == "") {
		log.Fatal("OBIS_TLS_CA, OBIS_TLS_CERT, and OBIS_TLS_KEY must be configured together")
	}

	var httpClient *http.Client
	var secret []byte
	if tlsEnabled {
		caPEM, err := os.ReadFile(caPath)
		if err != nil {
			log.Fatal(err)
		}
		certificatePEM, err := os.ReadFile(certPath)
		if err != nil {
			log.Fatal(err)
		}
		privateKeyPEM, err := os.ReadFile(keyPath)
		if err != nil {
			log.Fatal(err)
		}
		serverName := envOr("OBIS_TLS_SERVER_NAME", parsed.Hostname())
		httpClient, err = peer.NewTLS13HTTPClient(caPEM, certificatePEM, privateKeyPEM, serverName, remotePeerID)
		if err != nil {
			log.Fatal(err)
		}
	} else {
		if parsed.Scheme != "http" {
			log.Fatal("HMAC development mode is loopback HTTP only")
		}
		secret = []byte(required("OBIS_TEST_SECRET"))
		httpClient = &http.Client{Timeout: 5 * time.Second}
	}

	client, err := peer.NewClient(peer.ClientConfig{
		LocalPeerID: localPeerID, RemotePeerID: remotePeerID,
		KeyID: keyID, PrincipalRef: principal,
		Secret: secret, Scopes: map[string]bool{"catalog:read": true},
		HTTPClient: httpClient, MTLS: tlsEnabled,
	})
	if err != nil {
		log.Fatal(err)
	}
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()
	response, err := client.Invoke(ctx, endpoint, "catalog.lookup", "1.0", map[string]any{
		"item_id": required("OBIS_TEST_ITEM_ID"),
	})
	if err != nil {
		log.Fatal(err)
	}
	if err := json.NewEncoder(os.Stdout).Encode(response); err != nil {
		log.Fatal(err)
	}
}
