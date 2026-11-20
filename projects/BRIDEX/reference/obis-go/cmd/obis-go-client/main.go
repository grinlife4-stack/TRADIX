package main

import (
	"context"
	"encoding/json"
	"log"
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

func main() {
	endpoint := required("OBIS_REMOTE_ENDPOINT")
	parsed, err := url.Parse(endpoint)
	if err != nil {
		log.Fatal(err)
	}
	serverName := os.Getenv("OBIS_TLS_SERVER_NAME")
	if serverName == "" {
		serverName = parsed.Hostname()
	}
	caPEM, err := os.ReadFile(required("OBIS_TLS_CA"))
	if err != nil {
		log.Fatal(err)
	}
	certificatePEM, err := os.ReadFile(required("OBIS_TLS_CERT"))
	if err != nil {
		log.Fatal(err)
	}
	privateKeyPEM, err := os.ReadFile(required("OBIS_TLS_KEY"))
	if err != nil {
		log.Fatal(err)
	}
	httpClient, err := peer.NewTLS13HTTPClient(caPEM, certificatePEM, privateKeyPEM, serverName)
	if err != nil {
		log.Fatal(err)
	}
	client, err := peer.NewClient(peer.ClientConfig{
		LocalPeerID: "go-peer",
		RemotePeerID: "python-peer",
		KeyID: "go-key",
		PrincipalRef: "principal:go",
		Secret: []byte(required("OBIS_TEST_SECRET")),
		Scopes: map[string]bool{"catalog:read": true},
		HTTPClient: httpClient,
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
