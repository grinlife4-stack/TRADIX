package peer

import (
	"bytes"
	"crypto/tls"
	"crypto/x509"
	"crypto/hmac"
	"crypto/rand"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"math"
	"net/http"
	"strconv"
	"strings"
	"regexp"
	"sync"
	"time"
)

const (
	Protocol       = "obis"
	Version        = "0.1"
	MessagePath    = "/obis/v0.1/messages"
	MaxMessageSize = 64 * 1024
	MaxTTLSeconds  = 60
	ClockSkew      = 30
)

type Credential struct {
	KeyID        string
	PeerID       string
	PrincipalRef string
	Secret       []byte
	AllowedScopes map[string]bool
}

type Handler func(map[string]any) (map[string]any, error)

type Capability struct {
	Version        string
	RequiredScopes map[string]bool
	Handler        Handler
}

type Peer struct {
	ID           string
	Credential   Credential
	Capabilities map[string]Capability
	mu           sync.Mutex
	seen         map[string]time.Time
}

func NewPeer(id string, credential Credential) (*Peer, error) {
	if id == "" || credential.KeyID == "" || credential.PeerID == "" || credential.PrincipalRef == "" {
		return nil, errors.New("peer and credential identifiers are required")
	}
	if len(credential.Secret) < 32 || len(credential.AllowedScopes) == 0 {
		return nil, errors.New("reference credential requires a 32-byte secret and explicit scopes")
	}
	return &Peer{ID: id, Credential: credential, Capabilities: map[string]Capability{}, seen: map[string]time.Time{}}, nil
}

func (p *Peer) RegisterCapability(id, version string, required map[string]bool, handler Handler) error {
	if id == "" || version == "" || len(required) == 0 || handler == nil {
		return errors.New("capability id, version, scopes and handler are required")
	}
	if _, exists := p.Capabilities[id]; exists {
		return errors.New("duplicate capability")
	}
	p.Capabilities[id] = Capability{Version: version, RequiredScopes: required, Handler: handler}
	return nil
}

func CanonicalJSON(value any) ([]byte, error) {
	var out bytes.Buffer
	encoder := json.NewEncoder(&out)
	encoder.SetEscapeHTML(false)
	if err := encoder.Encode(value); err != nil {
		return nil, err
	}
	return bytes.TrimSuffix(out.Bytes(), []byte("\n")), nil
}

func Sign(value any, secret []byte) (string, error) {
	body, err := CanonicalJSON(value)
	if err != nil {
		return "", err
	}
	mac := hmac.New(sha256.New, secret)
	_, _ = mac.Write(body)
	return hex.EncodeToString(mac.Sum(nil)), nil
}

func Verify(value any, secret []byte, signature string) bool {
	got, err := hex.DecodeString(signature)
	if err != nil {
		return false
	}
	expected, err := Sign(value, secret)
	if err != nil {
		return false
	}
	want, _ := hex.DecodeString(expected)
	return hmac.Equal(got, want)
}

func decodeObject(raw []byte) (map[string]any, error) {
	decoder := json.NewDecoder(bytes.NewReader(raw))
	decoder.UseNumber()
	var value map[string]any
	if err := decoder.Decode(&value); err != nil {
		return nil, err
	}
	if value == nil {
		return nil, errors.New("message must be an object")
	}
	var extra any
	if err := decoder.Decode(&extra); err != io.EOF {
		return nil, errors.New("trailing JSON content")
	}
	return value, nil
}

func exactKeys(value map[string]any, required ...string) bool {
	if len(value) != len(required) {
		return false
	}
	for _, key := range required {
		if _, ok := value[key]; !ok {
			return false
		}
	}
	return true
}

func stringField(value map[string]any, key string) (string, bool) {
	text, ok := value[key].(string)
	return text, ok && text != ""
}

func numberField(value map[string]any, key string) (float64, bool) {
	number, ok := value[key].(json.Number)
	if !ok {
		return 0, false
	}
	result, err := strconv.ParseFloat(string(number), 64)
	return result, err == nil && !math.IsNaN(result) && !math.IsInf(result, 0)
}

func peerRef(value any) (string, bool) {
	object, ok := value.(map[string]any)
	if !ok || !exactKeys(object, "peer_id") {
		return "", false
	}
	return stringField(object, "peer_id")
}

func stringSet(value any) (map[string]bool, bool) {
	list, ok := value.([]any)
	if !ok || len(list) == 0 {
		return nil, false
	}
	result := make(map[string]bool, len(list))
	for _, item := range list {
		text, ok := item.(string)
		if !ok || text == "" || result[text] {
			return nil, false
		}
		result[text] = true
	}
	return result, true
}

func (p *Peer) validate(message map[string]any, keyID, signature string, now time.Time) (map[string]any, Capability, error) {
	if !exactKeys(message, "protocol", "version", "message_type", "message_id", "nonce", "sender", "recipient", "issued_at", "expires_at", "capability", "authorization", "payload") {
		return nil, Capability{}, errors.New("protocol.invalid_message")
	}
	if message["protocol"] != Protocol || message["version"] != Version || message["message_type"] != "request" {
		return nil, Capability{}, errors.New("protocol.unsupported_version")
	}
	messageID, ok := stringField(message, "message_id")
	if !ok || len(messageID) > 200 {
		return nil, Capability{}, errors.New("protocol.invalid_message_id")
	}
	nonce, ok := stringField(message, "nonce")
	if !ok || len(nonce) > 200 {
		return nil, Capability{}, errors.New("protocol.invalid_nonce")
	}
	issued, ok1 := numberField(message, "issued_at")
	expires, ok2 := numberField(message, "expires_at")
	current := float64(now.UnixNano()) / 1e9
	if !ok1 || !ok2 || issued > current+ClockSkew || expires <= issued || expires-issued > MaxTTLSeconds || expires < current-ClockSkew {
		return nil, Capability{}, errors.New("request.expired_or_invalid")
	}
	sender, ok1 := peerRef(message["sender"])
	recipient, ok2 := peerRef(message["recipient"])
	if !ok1 || !ok2 || sender != p.Credential.PeerID || recipient != p.ID {
		return nil, Capability{}, errors.New("identity.peer_mismatch")
	}
	if keyID != p.Credential.KeyID || !Verify(message, p.Credential.Secret, signature) {
		return nil, Capability{}, errors.New("identity.authentication_failed")
	}
	auth, ok := message["authorization"].(map[string]any)
	if !ok || !exactKeys(auth, "principal_ref", "scopes") {
		return nil, Capability{}, errors.New("authorization.invalid")
	}
	principal, ok := stringField(auth, "principal_ref")
	if !ok || principal != p.Credential.PrincipalRef {
		return nil, Capability{}, errors.New("identity.principal_mismatch")
	}
	requested, ok := stringSet(auth["scopes"])
	if !ok {
		return nil, Capability{}, errors.New("authorization.invalid_scopes")
	}
	capRef, ok := message["capability"].(map[string]any)
	if !ok || !exactKeys(capRef, "id", "version") {
		return nil, Capability{}, errors.New("capability.invalid")
	}
	capID, ok1 := stringField(capRef, "id")
	capVersion, ok2 := stringField(capRef, "version")
	if !ok1 || !ok2 {
		return nil, Capability{}, errors.New("capability.invalid")
	}
	payload, ok := message["payload"].(map[string]any)
	if !ok {
		return nil, Capability{}, errors.New("payload.invalid")
	}
	capability, exists := p.Capabilities[capID]
	if !exists || capability.Version != capVersion {
		return nil, Capability{}, errors.New("capability.unknown")
	}
	for scope := range capability.RequiredScopes {
		if !requested[scope] || !p.Credential.AllowedScopes[scope] {
			return nil, Capability{}, errors.New("authorization.denied")
		}
	}
	for scope := range requested {
		if !p.Credential.AllowedScopes[scope] {
			return nil, Capability{}, errors.New("authorization.denied")
		}
	}
	p.mu.Lock()
	defer p.mu.Unlock()
	for key, until := range p.seen {
		if !until.After(now) {
			delete(p.seen, key)
		}
	}
	replayKey := keyID + ":" + nonce
	if _, exists := p.seen[replayKey]; exists {
		return nil, Capability{}, errors.New("request.replay_detected")
	}
	p.seen[replayKey] = time.Unix(0, int64(expires*1e9))
	return payload, capability, nil
}

func randomID() string {
	raw := make([]byte, 16)
	if _, err := rand.Read(raw); err != nil {
		return strconv.FormatInt(time.Now().UnixNano(), 16)
	}
	return hex.EncodeToString(raw)
}


var peerIDPattern = regexp.MustCompile("^[a-z][a-z0-9-]{2,62}$")

func PeerIDFromCertificate(certificate *x509.Certificate) (string, error) {
	if certificate == nil {
		return "", errors.New("client certificate is missing")
	}
	var found []string
	for _, uri := range certificate.URIs {
		if uri.Scheme == "urn" && strings.HasPrefix(uri.Opaque, "obis:peer:") {
			found = append(found, strings.TrimPrefix(uri.Opaque, "obis:peer:"))
		}
	}
	if len(found) != 1 || !peerIDPattern.MatchString(found[0]) {
		return "", errors.New("certificate must contain exactly one valid OBIS peer URI SAN")
	}
	return found[0], nil
}

func (p *Peer) ServeHTTP(writer http.ResponseWriter, request *http.Request) {
	if request.URL.Path == "/healthz" && request.Method == http.MethodGet {
		writer.WriteHeader(http.StatusNoContent)
		return
	}
	if request.Method != http.MethodPost || request.URL.Path != MessagePath {
		http.NotFound(writer, request)
		return
	}
	if !strings.HasPrefix(request.Header.Get("Content-Type"), "application/obis+json") {
		http.Error(writer, "unsupported content type", http.StatusUnsupportedMediaType)
		return
	}
	request.Body = http.MaxBytesReader(writer, request.Body, MaxMessageSize)
	raw, err := io.ReadAll(request.Body)
	if err != nil || len(raw) == 0 {
		http.Error(writer, "invalid message body", http.StatusBadRequest)
		return
	}
	message, err := decodeObject(raw)
	if err != nil {
		http.Error(writer, "invalid JSON message", http.StatusBadRequest)
		return
	}
	if request.TLS != nil {
		if request.TLS.Version != tls.VersionTLS13 || request.TLS.NegotiatedProtocol != "obis/1" || len(request.TLS.PeerCertificates) == 0 {
			http.Error(writer, "OBIS requires TLS 1.3 mTLS and ALPN obis/1", http.StatusForbidden)
			return
		}
		certificatePeerID, certErr := PeerIDFromCertificate(request.TLS.PeerCertificates[0])
		senderPeerID, senderOK := peerRef(message["sender"])
		if certErr != nil || !senderOK || certificatePeerID != senderPeerID {
			http.Error(writer, "TLS certificate peer identity mismatch", http.StatusForbidden)
			return
		}
	}
	payload, capability, err := p.validate(message, request.Header.Get("X-OBIS-Key-Id"), request.Header.Get("X-OBIS-Signature"), time.Now())
	if err != nil {
		http.Error(writer, err.Error(), http.StatusForbidden)
		return
	}
	result, err := capability.Handler(payload)
	if err != nil || result == nil {
		http.Error(writer, "capability execution failed", http.StatusInternalServerError)
		return
	}
	sender, _ := peerRef(message["sender"])
	response := map[string]any{
		"protocol": Protocol,
		"version": Version,
		"message_type": "response",
		"message_id": randomID(),
		"correlation_id": message["message_id"],
		"sender": map[string]any{"peer_id": p.ID},
		"recipient": map[string]any{"peer_id": sender},
		"issued_at": time.Now().Unix(),
		"outcome": "succeeded",
		"result": result,
	}
	body, err := CanonicalJSON(response)
	if err != nil || len(body) > MaxMessageSize {
		http.Error(writer, "invalid response", http.StatusInternalServerError)
		return
	}
	signature, err := Sign(response, p.Credential.Secret)
	if err != nil {
		http.Error(writer, "response signing failed", http.StatusInternalServerError)
		return
	}
	writer.Header().Set("Content-Type", "application/obis+json")
	writer.Header().Set("X-OBIS-Signature", signature)
	writer.WriteHeader(http.StatusOK)
	_, _ = writer.Write(body)
}

func (p *Peer) String() string {
	return fmt.Sprintf("OBIS peer %s (%s)", p.ID, p.Credential.PeerID)
}
