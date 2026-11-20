package main

import (
	"crypto/tls"
	"crypto/x509"
	"log"
	"net"
	"net/http"
	"os"
	"strings"
	"time"

	"example.com/bridex/obis-go/peer"
)

func envOr(name, fallback string) string {
	if value := os.Getenv(name); value != "" {
		return value
	}
	return fallback
}

func required(name string) string {
	value := os.Getenv(name)
	if value == "" {
		log.Fatalf("%s is required", name)
	}
	return value
}

func parseScopes(value string) map[string]bool {
	result := map[string]bool{}
	for _, scope := range strings.Split(value, ",") {
		scope = strings.TrimSpace(scope)
		if scope != "" {
			result[scope] = true
		}
	}
	return result
}

func main() {
	address := envOr("OBIS_LISTEN_ADDR", "127.0.0.1:18081")
	host, _, err := net.SplitHostPort(address)
	if err != nil || (host != "127.0.0.1" && host != "::1" && host != "localhost") {
		log.Fatal("reference peer is loopback-only")
	}

	certPath := os.Getenv("OBIS_TLS_CERT")
	keyPath := os.Getenv("OBIS_TLS_KEY")
	caPath := os.Getenv("OBIS_TLS_CA")
	tlsEnabled := certPath != "" || keyPath != "" || caPath != ""
	if tlsEnabled && (certPath == "" || keyPath == "" || caPath == "") {
		log.Fatal("OBIS_TLS_CERT, OBIS_TLS_KEY, and OBIS_TLS_CA must be configured together")
	}

	credential := peer.Credential{
		KeyID:         envOr("OBIS_CLIENT_KEY_ID", "python-key"),
		PeerID:        envOr("OBIS_CLIENT_PEER_ID", "python-peer"),
		PrincipalRef:  envOr("OBIS_CLIENT_PRINCIPAL", "principal:python"),
		AllowedScopes: parseScopes(envOr("OBIS_CLIENT_SCOPES", "catalog:read")),
	}
	if tlsEnabled {
		credential.CertificateURI = required("OBIS_CLIENT_CERT_URI")
		credential.CertificateSHA256 = required("OBIS_CLIENT_CERT_SHA256")
	} else {
		credential.Secret = []byte(required("OBIS_TEST_SECRET"))
	}

	serverPeer, err := peer.NewPeer(envOr("OBIS_SERVER_PEER_ID", "go-peer"), credential)
	if err != nil {
		log.Fatal(err)
	}
	if err := serverPeer.RegisterCapability(
		"catalog.lookup", "1.0", map[string]bool{"catalog:read": true},
		func(payload map[string]any) (map[string]any, error) {
			itemID, ok := payload["item_id"].(string)
			if !ok || itemID == "" {
				return nil, http.ErrBodyNotAllowed
			}
			return map[string]any{"accepted": true, "item_id": itemID, "served_by": "go-peer"}, nil
		},
	); err != nil {
		log.Fatal(err)
	}

	server := &http.Server{
		Addr: address, Handler: serverPeer,
		ReadHeaderTimeout: 3 * time.Second,
		ReadTimeout: 5 * time.Second,
		WriteTimeout: 5 * time.Second,
		IdleTimeout: 10 * time.Second,
	}
	if !tlsEnabled {
		log.Fatal(server.ListenAndServe())
	}

	certificate, err := tls.LoadX509KeyPair(certPath, keyPath)
	if err != nil {
		log.Fatal(err)
	}
	caPEM, err := os.ReadFile(caPath)
	if err != nil {
		log.Fatal(err)
	}
	clientRoots := x509.NewCertPool()
	if !clientRoots.AppendCertsFromPEM(caPEM) {
		log.Fatal("OBIS_TLS_CA contains no valid certificate")
	}
	tlsConfig := &tls.Config{
		MinVersion: tls.VersionTLS13,
		MaxVersion: tls.VersionTLS13,
		ClientAuth: tls.RequireAndVerifyClientCert,
		ClientCAs: clientRoots,
		Certificates: []tls.Certificate{certificate},
		NextProtos: []string{"http/1.1"},
	}
	listener, err := net.Listen("tcp", address)
	if err != nil {
		log.Fatal(err)
	}
	server.TLSConfig = tlsConfig
	log.Fatal(server.Serve(tls.NewListener(listener, tlsConfig)))
}
