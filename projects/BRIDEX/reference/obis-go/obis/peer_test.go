package obis

import (
	"encoding/json"
	"os"
	"path/filepath"
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
	request:=map[string]any{"protocol":Protocol,"version":Version,"message_type":"request","message_id":"req-1","nonce":"nonce-1","sender":map[string]any{"peer_id":"peer:python"},"recipient":map[string]any{"peer_id":"peer:go"},"issued_at":json.Number(time.Unix(now,0).Format("1136239445")),"expires_at":json.Number(time.Unix(now+30,0).Format("1136239445")),"capability":map[string]any{"id":"records.read","version":"1.0"},"authorization":map[string]any{"principal_ref":"principal:python","scopes":[]any{"records:read"}},"payload":map[string]any{"record_id":"r-1"}}
	// Use integer JSON timestamps to match the wire representation.
	request["issued_at"]=json.Number(time.Unix(now,0).Format("1136239445"))
	request["expires_at"]=json.Number(time.Unix(now+30,0).Format("1136239445"))
	sig,err:=Sign(request,secret);if err!=nil{t.Fatal(err)}
	response,_,protocolErr:=p.Handle(request,"py-key",sig);if protocolErr!=nil{t.Fatal(protocolErr)}
	if response["outcome"]!="succeeded"{t.Fatalf("unexpected response: %#v",response)}
	_,_,protocolErr=p.Handle(request,"py-key",sig);if protocolErr==nil||protocolErr.Code!="request.replay_detected"{t.Fatalf("expected replay rejection, got %#v",protocolErr)}
}
func TestPublishedRequestVectors(t *testing.T) {
	path:=filepath.Join("..","..","..","..","..","..","standards","obis","0.1","conformance","vectors.json")
	raw,err:=os.ReadFile(path);if err!=nil{t.Skipf("repository conformance vectors not present in standalone checkout: %v",err)}
	var suite struct{Vectors []struct{ID string `json:"id"`; Expected string `json:"expected"`; Message map[string]any `json:"message"`} `json:"vectors"`}
	if err=json.Unmarshal(raw,&suite);err!=nil{t.Fatal(err)}
	now:=time.Unix(1795168810,0)
	for _,v:=range suite.Vectors{
		if v.Message["message_type"]!="request"{continue}
		err:=ValidateRequest(v.Message,now)
		actual:="accept";if err!=nil{actual="reject"}
		if actual!=v.Expected{t.Errorf("%s: expected %s, got %s (%v)",v.ID,v.Expected,actual,err)}
	}
}
