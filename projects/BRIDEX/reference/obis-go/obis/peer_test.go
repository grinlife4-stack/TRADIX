package obis

import (
	"errors"
	"encoding/json"
	"bytes"
	"os"
	"path/filepath"
	"strconv"
	"testing"
	"time"
)

func TestDecodeStrictRejectsDuplicateKeys(t *testing.T) {
	if _,err:=DecodeStrict([]byte(`{"a":1,"a":2}`));err==nil{t.Fatal("duplicate key accepted")}
	if _,err:=DecodeStrict([]byte(`{"a":1} {"b":2}`));err==nil{t.Fatal("trailing value accepted")}
}
func TestCanonicalJSONMatchesDevelopmentFixture(t *testing.T) {
	value:=map[string]any{"z":json.Number("2"),"a":"plain"}
	got,err:=CanonicalJSON(value);if err!=nil{t.Fatal(err)}
	if string(got)!=`{"a":"plain","z":2}`{t.Fatalf("unexpected canonical bytes: %s",got)}
}
func TestPeerAcceptsRequestAndRejectsReplay(t *testing.T) {
	secret:=[]byte("0123456789abcdef0123456789abcdef")
	p,err:=NewPeer("peer:go");if err!=nil{t.Fatal(err)}
	if err=p.AddCredential(Credential{KeyID:"py-key",PeerID:"peer:python",PrincipalRef:"principal:python",Secret:secret,AllowedScopes:map[string]bool{"records:read":true}});err!=nil{t.Fatal(err)}
	if err=p.RegisterCapability(Capability{ID:"records.read",Version:"1.0",RequiredScopes:map[string]bool{"records:read":true},Handler:func(payload map[string]any)(map[string]any,error){return map[string]any{"record_id":payload["record_id"]},nil}});err!=nil{t.Fatal(err)}
	now:=time.Now().Unix()
	request:=map[string]any{"protocol":Protocol,"version":Version,"message_type":"request","message_id":"req-1","nonce":"nonce-1","sender":map[string]any{"peer_id":"peer:python"},"recipient":map[string]any{"peer_id":"peer:go"},"issued_at":json.Number(strconv.FormatInt(now,10)),"expires_at":json.Number(strconv.FormatInt(now+30,10)),"capability":map[string]any{"id":"records.read","version":"1.0"},"authorization":map[string]any{"principal_ref":"principal:python","scopes":[]any{"records:read"}},"payload":map[string]any{"record_id":"r-1"}}
	sig,err:=Sign(request,secret);if err!=nil{t.Fatal(err)}
	response,_,protocolErr:=p.Handle(request,"py-key",sig);if protocolErr!=nil{t.Fatal(protocolErr)}
	if response["outcome"]!="succeeded"{t.Fatalf("unexpected response: %#v",response)}
	_,_,protocolErr=p.Handle(request,"py-key",sig);if protocolErr==nil||protocolErr.Code!="request.replay_detected"{t.Fatalf("expected replay rejection, got %#v",protocolErr)}
}
func TestPublishedRequestVectors(t *testing.T) {
	path:=filepath.Join("..","..","..","..","..","standards","obis","0.1","conformance","vectors.json")
	raw,err:=os.ReadFile(path);if err!=nil{t.Skipf("repository conformance vectors not present in standalone checkout: %v",err)}
	var suite struct{Vectors []struct{ID string `json:"id"`; Expected string `json:"expected"`; Message map[string]any `json:"message"`} `json:"vectors"`}
	dec:=json.NewDecoder(bytes.NewReader(raw));dec.UseNumber();if err=dec.Decode(&suite);err!=nil{t.Fatal(err)}
	now:=time.Unix(1795168810,0)
	for _,v:=range suite.Vectors{
		if v.Message["message_type"]!="request"{continue}
		err:=ValidateRequest(v.Message,now)
		actual:="accept";if err!=nil{actual="reject"}
		if actual!=v.Expected{t.Errorf("%s: expected %s, got %s (%v)",v.ID,v.Expected,actual,err)}
	}
}

func TestPublishedMessageVectorsAcrossEnvelopeTypes(t *testing.T) {
	path := filepath.Join("..", "..", "..", "..", "..", "standards", "obis", "0.1", "conformance", "vectors.json")
	raw, err := os.ReadFile(path)
	if err != nil { t.Skipf("repository conformance vectors not present in standalone checkout: %v", err) }
	var suite struct { Vectors []struct { ID string `json:"id"`; Expected string `json:"expected"`; Message map[string]any `json:"message"` } `json:"vectors"` }
	dec := json.NewDecoder(bytes.NewReader(raw)); dec.UseNumber()
	if err = dec.Decode(&suite); err != nil { t.Fatal(err) }
	for _, vector := range suite.Vectors {
		var validationErr error
		switch vector.Message["message_type"] {
		case "request":
			if requestErr := ValidateRequest(vector.Message, time.Unix(1795168810, 0)); requestErr != nil { validationErr = requestErr }
		case "response":
			sender, _ := obj(vector.Message, "sender")
			recipient, _ := obj(vector.Message, "recipient")
			senderID, _ := str(sender, "peer_id")
			recipientID, _ := str(recipient, "peer_id")
			correlation, _ := str(vector.Message, "correlation_id")
			if vector.Message["outcome"] == "succeeded" {
				validationErr = validateSuccessResponse(vector.Message, correlation, recipientID, senderID)
			} else {
				validationErr = validateFailureResponse(vector.Message, correlation, recipientID, senderID)
			}
		default:
			validationErr = errors.New("unsupported message type")
		}
		actual := "accept"
		if validationErr != nil { actual = "reject" }
		if actual != vector.Expected { t.Errorf("%s: expected %s, got %s (%v)", vector.ID, vector.Expected, actual, validationErr) }
	}
}


func validNegativeTestRequest(now time.Time) map[string]any {
	return map[string]any{
		"protocol": Protocol,
		"version": Version,
		"message_type": "request",
		"message_id": "negative-test-request",
		"nonce": "negative-test-nonce",
		"sender": map[string]any{"peer_id": "peer:python"},
		"recipient": map[string]any{"peer_id": "peer:go"},
		"issued_at": json.Number(strconv.FormatInt(now.Unix(), 10)),
		"expires_at": json.Number(strconv.FormatInt(now.Add(30*time.Second).Unix(), 10)),
		"capability": map[string]any{"id": "records.read", "version": "1.0"},
		"authorization": map[string]any{"principal_ref": "principal:python", "scopes": []any{"records:read"}},
		"payload": map[string]any{"record_id": "negative-case"},
	}
}

func newNegativeTestPeer(t *testing.T, handlerCalls *int) (*Peer, []byte) {
	t.Helper()
	secret := []byte("0123456789abcdef0123456789abcdef")
	peer, err := NewPeer("peer:go")
	if err != nil { t.Fatal(err) }
	err = peer.AddCredential(Credential{
		KeyID: "python-key", PeerID: "peer:python", PrincipalRef: "principal:python",
		Secret: secret, AllowedScopes: map[string]bool{"records:read": true},
	})
	if err != nil { t.Fatal(err) }
	err = peer.RegisterCapability(Capability{
		ID: "records.read", Version: "1.0",
		RequiredScopes: map[string]bool{"records:read": true},
		Handler: func(payload map[string]any) (map[string]any, error) {
			*handlerCalls++
			return map[string]any{"record_id": payload["record_id"]}, nil
		},
	})
	if err != nil { t.Fatal(err) }
	return peer, secret
}

func TestValidateRequestRejectsMalformedNegativeMatrix(t *testing.T) {
	now := time.Unix(1795168810, 0)
	cases := []struct {
		name string
		mutate func(map[string]any)
	}{
		{"unknown top-level field", func(m map[string]any) { m["unexpected"] = true }},
		{"unsupported version", func(m map[string]any) { m["version"] = "0.2" }},
		{"wrong message type", func(m map[string]any) { m["message_type"] = "response" }},
		{"string timestamp", func(m map[string]any) { m["issued_at"] = "1795168810" }},
		{"excessive ttl", func(m map[string]any) { m["expires_at"] = json.Number("1795169000") }},
		{"duplicate scopes", func(m map[string]any) { m["authorization"].(map[string]any)["scopes"] = []any{"records:read", "records:read"} }},
		{"unknown nested field", func(m map[string]any) { m["sender"].(map[string]any)["extra"] = "x" }},
		{"non-object payload", func(m map[string]any) { m["payload"] = []any{"not", "an", "object"} }},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			request := validNegativeTestRequest(now)
			tc.mutate(request)
			if err := ValidateRequest(request, now); err == nil {
				t.Fatal("malformed request was accepted")
			}
		})
	}
}

func TestHandleRejectsAuthenticationFailuresBeforeCapabilityExecution(t *testing.T) {
	cases := []struct {
		name string
		keyID string
		signature func(map[string]any, []byte) string
		mutate func(map[string]any)
	}{
		{"unknown key", "missing-key", func(_ map[string]any, _ []byte) string { return "00" }, nil},
		{"invalid signature", "python-key", func(_ map[string]any, _ []byte) string { return "00" }, nil},
		{"principal mismatch", "python-key", func(m map[string]any, secret []byte) string { sig, _ := Sign(m, secret); return sig }, func(m map[string]any) { m["authorization"].(map[string]any)["principal_ref"] = "principal:other" }},
		{"sender mismatch", "python-key", func(m map[string]any, secret []byte) string { sig, _ := Sign(m, secret); return sig }, func(m map[string]any) { m["sender"].(map[string]any)["peer_id"] = "peer:other" }},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			calls := 0
			peer, secret := newNegativeTestPeer(t, &calls)
			request := validNegativeTestRequest(time.Now())
			if tc.mutate != nil { tc.mutate(request) }
			signature := tc.signature(request, secret)
			_, _, protocolErr := peer.Handle(request, tc.keyID, signature)
			if protocolErr == nil || protocolErr.Code != "identity.authentication_failed" && protocolErr.Code != "identity.unknown_peer" {
				t.Fatalf("expected authentication rejection, got %#v", protocolErr)
			}
			if calls != 0 { t.Fatalf("capability handler ran %d times after authentication failure", calls) }
		})
	}
}

func TestHandleRejectsUnauthorizedScopeBeforeCapabilityExecution(t *testing.T) {
	calls := 0
	peer, secret := newNegativeTestPeer(t, &calls)
	request := validNegativeTestRequest(time.Now())
	request["authorization"].(map[string]any)["scopes"] = []any{"records:write"}
	signature, err := Sign(request, secret)
	if err != nil { t.Fatal(err) }
	_, _, protocolErr := peer.Handle(request, "python-key", signature)
	if protocolErr == nil || protocolErr.Code != "authorization.denied" {
		t.Fatalf("expected authorization.denied, got %#v", protocolErr)
	}
	if calls != 0 { t.Fatalf("capability handler ran %d times after authorization denial", calls) }
}


func TestReplayDoesNotExecuteCapabilityTwice(t *testing.T) {
	calls := 0
	peer, secret := newNegativeTestPeer(t, &calls)
	request := validNegativeTestRequest(time.Now())
	signature, err := Sign(request, secret)
	if err != nil { t.Fatal(err) }

	if _, _, protocolErr := peer.Handle(request, "python-key", signature); protocolErr != nil {
		t.Fatalf("first request failed: %v", protocolErr)
	}
	if calls != 1 { t.Fatalf("expected one execution, got %d", calls) }

	_, _, protocolErr := peer.Handle(request, "python-key", signature)
	if protocolErr == nil || protocolErr.Code != "request.replay_detected" {
		t.Fatalf("expected replay rejection, got %#v", protocolErr)
	}
	if calls != 1 { t.Fatalf("replayed request executed capability again; calls=%d", calls) }
}
