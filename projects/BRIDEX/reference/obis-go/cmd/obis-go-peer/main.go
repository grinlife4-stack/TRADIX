package main

import (
	"crypto/tls"
	"crypto/x509"
	"log"
	"net"
	"net/http"
	"os"
	"time"

	"example.com/bridex/obis-go/peer"
)

func main() {
	secret := []byte(os.Getenv("OBIS_TEST_SECRET"))
	if len(secret) < 32 {
		log.Fatal("OBIS_TEST_SECRET must contain at least 32 bytes")
	}
	address := os.Getenv("OBIS_LISTEN_ADDR")
	if address == "" {
		address = "127.0.0.1:18081"
	}
	host, _, err := net.SplitHostPort(address)
	if err != nil || (host != "127.0.0.1" && host != "::1" && host != "localhost") {
		log.Fatal("reference peer is loopback-only")
	}
	credential := peer.Credential{
		KeyID: "python-key",
		PeerID: "python-peer",
		PrincipalRef: "principal:python",
		Secret: secret,
		AllowedScopes: map[string]bool{"catalog:read": true},
	}
	serverPeer, err := peer.NewPeer("go-peer", credential)
	if err != nil {
		log.Fatal(err)
	}
	err = serverPeer.RegisterCapability("catalog.lookup", "1.0", map[string]bool{"catalog:read": true},
		func(payload map[string]any) (map[string]any, error) {
			itemID, ok := payload["item_id"].(string)
			if !ok || itemID == "" {
				return nil, http.ErrBodyNotAllowed
			}
			return map[string]any{"accepted": true, "item_id": itemID, "served_by": "go-peer"}, nil
		})
	if err != nil {
		log.Fatal(err)
	}
	server := &http.Server{
		Addr: address,
		Handler: serverPeer,
		ReadHeaderTimeout: 3 * time.Second,
		ReadTimeout: 5 * time.Second,
		WriteTimeout: 5 * time.Second,
		IdleTimeout: 10 * time.Second,
	}
	certPath := os.Getenv("OBIS_TLS_CERT")
	keyPath := os.Getenv("OBIS_TLS_KEY")
	caPath := os.Getenv("OBIS_TLS_CA")
	if certPath == "" && keyPath == "" && caPath == "" {
		log.Fatal(server.ListenAndServe())
	}
	if certPath == "" || keyPath == "" || caPath == "" {
		log.Fatal("OBIS_TLS_CERT, OBIS_TLS_KEY, and OBIS_TLS_CA must be configured together")
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
