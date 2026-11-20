package peer

import (
	"bytes"
	"context"
	"crypto/tls"
	"crypto/x509"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"sort"
	"strings"
	"time"
)

type ClientConfig struct {
	LocalPeerID  string
	RemotePeerID string
	KeyID        string
	PrincipalRef string
	Secret       []byte
	Scopes       map[string]bool
	HTTPClient   *http.Client
	MTLS         bool
}

type Client struct {
	config ClientConfig
}

func NewTLS13HTTPClient(caPEM, certificatePEM, privateKeyPEM []byte, serverName, expectedPeerID string) (*http.Client, error) {
	if len(caPEM) == 0 || len(certificatePEM) == 0 || len(privateKeyPEM) == 0 || serverName == "" || expectedPeerID == "" {
		return nil, errors.New("TLS CA, client certificate, private key, and server name are required")
	}
	roots := x509.NewCertPool()
	if !roots.AppendCertsFromPEM(caPEM) {
		return nil, errors.New("no valid CA certificate provided")
	}
	certificate, err := tls.X509KeyPair(certificatePEM, privateKeyPEM)
	if err != nil {
		return nil, err
	}
	transport := &http.Transport{
		TLSClientConfig: &tls.Config{
			RootCAs: roots,
			Certificates: []tls.Certificate{certificate},
			ServerName: serverName,
			MinVersion: tls.VersionTLS13,
			MaxVersion: tls.VersionTLS13,
			NextProtos: []string{"http/1.1"},
			VerifyConnection: func(state tls.ConnectionState) error {
				if len(state.PeerCertificates) == 0 {
					return errors.New("OBIS server certificate is missing")
				}
				peerID, err := PeerIDFromCertificate(state.PeerCertificates[0])
				if err != nil || peerID != expectedPeerID {
					return errors.New("OBIS server certificate peer identity mismatch")
				}
				return nil
			},
		},
	}
	return &http.Client{Transport: transport, Timeout: 5 * time.Second}, nil
}

func NewClient(config ClientConfig) (*Client, error) {
	if config.LocalPeerID == "" || config.RemotePeerID == "" || config.KeyID == "" || config.PrincipalRef == "" {
		return nil, errors.New("peer, key, and principal identifiers are required")
	}
	if len(config.Scopes) == 0 {
		return nil, errors.New("client requires explicit scopes")
	}
	if config.MTLS {
		if len(config.Secret) != 0 {
			return nil, errors.New("mTLS client must not carry an HMAC secret")
		}
	} else if len(config.Secret) < 32 {
		return nil, errors.New("development client requires a 32-byte secret")
	}
	if config.HTTPClient == nil {
		return nil, errors.New("explicit HTTP client is required")
	}
	return &Client{config: config}, nil
}

func (c *Client) Invoke(ctx context.Context, endpoint, capabilityID, capabilityVersion string, payload map[string]any) (map[string]any, error) {
	parsed, err := url.Parse(endpoint)
	if err != nil || parsed.Hostname() == "" || parsed.User != nil || parsed.Path != "" && parsed.Path != "/" || parsed.RawQuery != "" || parsed.Fragment != "" {
		return nil, errors.New("endpoint must be a bare peer base URL")
	}
	if parsed.Hostname() != "127.0.0.1" && parsed.Hostname() != "::1" && parsed.Hostname() != "localhost" {
		return nil, errors.New("reference client is loopback-only")
	}
	if parsed.Scheme != "http" && parsed.Scheme != "https" {
		return nil, errors.New("unsupported reference transport scheme")
	}
	if c.config.MTLS && parsed.Scheme != "https" {
		return nil, errors.New("OBIS mTLS client requires HTTPS")
	}
	if !c.config.MTLS && parsed.Scheme != "http" {
		return nil, errors.New("HMAC development profile is loopback HTTP only")
	}
	if capabilityID == "" || capabilityVersion == "" || payload == nil {
		return nil, errors.New("capability and payload are required")
	}
	scopes := make([]string, 0, len(c.config.Scopes))
	for scope := range c.config.Scopes {
		scopes = append(scopes, scope)
	}
	sort.Strings(scopes)
	issued := time.Now().Unix()
	messageID, nonce := randomID(), randomID()
	message := map[string]any{
		"protocol": Protocol,
		"version": Version,
		"message_type": "request",
		"message_id": messageID,
		"nonce": nonce,
		"sender": map[string]any{"peer_id": c.config.LocalPeerID},
		"recipient": map[string]any{"peer_id": c.config.RemotePeerID},
		"issued_at": issued,
		"expires_at": issued + MaxTTLSeconds,
		"capability": map[string]any{"id": capabilityID, "version": capabilityVersion},
		"authorization": map[string]any{"principal_ref": c.config.PrincipalRef, "scopes": scopes},
		"payload": payload,
	}
	body, err := CanonicalJSON(message)
	if err != nil {
		return nil, err
	}
	signature := ""
	if !c.config.MTLS {
		signature, err = Sign(message, c.config.Secret)
		if err != nil {
			return nil, err
		}
	}
	request, err := http.NewRequestWithContext(ctx, http.MethodPost, strings.TrimRight(endpoint, "/")+MessagePath, bytes.NewReader(body))
	if err != nil {
		return nil, err
	}
	request.Header.Set("Content-Type", "application/obis+json")
	request.Header.Set("X-OBIS-Key-Id", c.config.KeyID)
	if !c.config.MTLS {
		request.Header.Set("X-OBIS-Signature", signature)
	}
	response, err := c.config.HTTPClient.Do(request)
	if err != nil {
		return nil, fmt.Errorf("peer.unavailable: %w", err)
	}
	defer response.Body.Close()
	responseBody, err := io.ReadAll(io.LimitReader(response.Body, MaxMessageSize+1))
	if err != nil || len(responseBody) > MaxMessageSize {
		return nil, errors.New("response body invalid or too large")
	}
	if response.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("peer.request_rejected: HTTP %d", response.StatusCode)
	}
	if parsed.Scheme == "https" {
		if response.TLS == nil || response.TLS.Version != tls.VersionTLS13 || response.TLS.NegotiatedProtocol != "http/1.1" || len(response.TLS.PeerCertificates) == 0 {
			return nil, errors.New("TLS 1.3 HTTP/1.1 peer authentication missing")
		}
		serverPeerID, certErr := PeerIDFromCertificate(response.TLS.PeerCertificates[0])
		if certErr != nil || serverPeerID != c.config.RemotePeerID {
			return nil, errors.New("TLS server certificate peer identity mismatch")
		}
	}
	responseMessage, err := decodeObject(responseBody)
	if err != nil {
		return nil, errors.New("invalid OBIS response JSON")
	}
	if c.config.MTLS {
		if response.TLS == nil || response.TLS.Version != tls.VersionTLS13 || response.TLS.NegotiatedProtocol != "http/1.1" {
			return nil, errors.New("OBIS TLS 1.3 peer authentication missing")
		}
		if response.Header.Get("X-OBIS-Signature") != "" {
			return nil, errors.New("mTLS profile must not use HMAC response signatures")
		}
		serverPeerID, certErr := PeerIDFromCertificate(response.TLS.PeerCertificates[0])
		if certErr != nil || serverPeerID != c.config.RemotePeerID {
			return nil, errors.New("TLS server certificate peer identity mismatch")
		}
	} else if !Verify(responseMessage, c.config.Secret, response.Header.Get("X-OBIS-Signature")) {
		return nil, errors.New("OBIS response signature verification failed")
	}
	if !exactKeys(responseMessage, "protocol", "version", "message_type", "message_id", "correlation_id", "sender", "recipient", "issued_at", "outcome", "result") {
		return nil, errors.New("OBIS response envelope fields invalid")
	}
	sender, senderOK := peerRef(responseMessage["sender"])
	recipient, recipientOK := peerRef(responseMessage["recipient"])
	issuedAt, issuedOK := numberField(responseMessage, "issued_at")
	now := float64(time.Now().UnixNano()) / 1e9
	if responseMessage["protocol"] != Protocol || responseMessage["version"] != Version ||
		responseMessage["message_type"] != "response" || responseMessage["correlation_id"] != messageID ||
		!senderOK || sender != c.config.RemotePeerID || !recipientOK || recipient != c.config.LocalPeerID ||
		!issuedOK || issuedAt > now+ClockSkew || issuedAt < now-ClockSkew ||
		responseMessage["outcome"] != "succeeded" {
		return nil, errors.New("OBIS response identity, correlation, or outcome invalid")
	}
	if _, ok := responseMessage["result"].(map[string]any); !ok {
		return nil, errors.New("OBIS response result must be an object")
	}
	return responseMessage, nil
}
