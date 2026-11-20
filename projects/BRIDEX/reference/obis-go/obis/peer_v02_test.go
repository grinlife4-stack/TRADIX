package obis

import (
	"encoding/json"
	"strconv"
	"path/filepath"
	"testing"
	"time"
)

func testV02Message(t *testing.T, secret []byte, nonce, attempt string, operationID, idem, requestHash string) (map[string]any,string) {
	t.Helper()
	now := time.Now().Unix()
	message := map[string]any{
		"protocol":"obis","version":"0.2","message_type":"request",
		"message_id":"message-"+nonce,"nonce":nonce,"attempt_id":attempt,
		"sender":map[string]any{"peer_id":"caller"},
		"recipient":map[string]any{"peer_id":"provider"},
		"issued_at":json.Number(fmtInt(now)),"expires_at":json.Number(fmtInt(now+45)),
		"capability":map[string]any{"id":"sample.read","version":"1.0"},
		"authorization":map[string]any{"principal_ref":"principal-a","scopes":[]any{"sample.read"}},
		"operation":map[string]any{"operation_id":operationID,"idempotency_key":idem,"request_hash":requestHash,"expires_at":json.Number(fmtInt(now+3600))},
		"payload":map[string]any{"item":"alpha"},
	}
	hash,err := OperationRequestHash(message)
	if err != nil { t.Fatal(err) }
	message["operation"].(map[string]any)["request_hash"] = hash
	signature,err := Sign(message,secret)
	if err != nil { t.Fatal(err) }
	return message,signature
}

func fmtInt(value int64) string { return strconv.FormatInt(value,10) }

func TestPeerV02DurableIdempotencyAndStatus(t *testing.T) {
	dir := t.TempDir()
	ledger,err := NewFileOperationLedger(filepath.Join(dir,"operations.json"))
	if err != nil { t.Fatal(err) }
	peer,err := NewPeer("provider")
	if err != nil { t.Fatal(err) }
	secret := []byte("0123456789abcdef0123456789abcdef")
	if err := peer.AddCredential(Credential{KeyID:"caller-key",PeerID:"caller",PrincipalRef:"principal-a",Secret:secret,AllowedScopes:map[string]bool{"sample.read":true}}); err != nil { t.Fatal(err) }
	executions := 0
	p02,err := NewPeerV02(peer,ledger)
	if err != nil { t.Fatal(err) }
	if err := p02.RegisterCapability("sample.read","1.0",map[string]bool{"sample.read":true},func(payload map[string]any)(map[string]any,error){
		executions++
		return map[string]any{"value":"ok"},nil
	},"IDEMPOTENT"); err != nil { t.Fatal(err) }

	first,sig := testV02Message(t,secret,"nonce-1","attempt-1","op-1","idem-1","")
	response,responseSecret,protocolErr := p02.Handle(first,"caller-key",sig)
	if protocolErr != nil { t.Fatal(protocolErr) }
	if len(responseSecret)==0 || response["message_type"]!="operation_response" { t.Fatal("invalid operation response") }
	op := response["operation"].(map[string]any)
	if op["state"]!="SUCCEEDED" || executions!=1 { t.Fatalf("unexpected first outcome: state=%v executions=%d",op["state"],executions) }

	// A new transport attempt with the same idempotency identity must replay the stored result.
	second,secondSig := testV02Message(t,secret,"nonce-2","attempt-2","op-1","idem-1","")
	response2,_,protocolErr := p02.Handle(second,"caller-key",secondSig)
	if protocolErr != nil { t.Fatal(protocolErr) }
	op2 := response2["operation"].(map[string]any)
	if op2["state"]!="SUCCEEDED" || executions!=1 { t.Fatalf("idempotent retry re-executed: state=%v executions=%d",op2["state"],executions) }

	status := map[string]any{
		"protocol":"obis","version":"0.2","message_type":"operation_status_request",
		"message_id":"status-1","nonce":"nonce-status","attempt_id":"attempt-status",
		"sender":map[string]any{"peer_id":"caller"},"recipient":map[string]any{"peer_id":"provider"},
		"issued_at":json.Number(fmtInt(time.Now().Unix())),"expires_at":json.Number(fmtInt(time.Now().Unix()+45)),
		"capability":map[string]any{"id":"sample.read","version":"1.0"},
		"authorization":map[string]any{"principal_ref":"principal-a","scopes":[]any{"sample.read"}},
		"operation_id":"op-1",
	}
	statusSig,err := Sign(status,secret); if err != nil { t.Fatal(err) }
	statusResponse,_,statusErr := p02.Handle(status,"caller-key",statusSig)
	if statusErr != nil { t.Fatal(statusErr) }
	if statusResponse["operation"].(map[string]any)["state"]!="SUCCEEDED" { t.Fatal("status query did not return committed result") }
}

func TestPeerV02RecoversRunningOperationAsUnknown(t *testing.T) {
	dir := t.TempDir()
	ledger,err := NewFileOperationLedger(filepath.Join(dir,"operations.json")); if err != nil { t.Fatal(err) }
	idemHash,err := ledger.IdempotencyKeyHash("idem-crash"); if err != nil { t.Fatal(err) }
	record,created,err := ledger.Reserve(OperationRecord{
		OperationID:"op-crash",PeerID:"caller",PrincipalRef:"principal-a",
		CapabilityID:"sample.read",CapabilityVersion:"1.0",
		IdempotencyKeyHash:idemHash,RequestHash:"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
		ExpiresAt:float64(time.Now().Unix()+3600),
	},float64(time.Now().Unix()))
	if err != nil || !created { t.Fatalf("reserve failed: %v",err) }
	if _,err := ledger.Transition(record.OperationID,"RUNNING",float64(time.Now().Unix()),nil,"",""); err != nil { t.Fatal(err) }
	peer,err := NewPeer("provider"); if err != nil { t.Fatal(err) }
	restarted,err := NewPeerV02(peer,ledger); if err != nil { t.Fatal(err) }
	_ = restarted
	recovered,err := ledger.Get("op-crash","caller","principal-a","sample.read","1.0")
	if err != nil { t.Fatal(err) }
	if recovered.State!="UNKNOWN" || recovered.FailureCode!="operation.outcome_unknown" { t.Fatalf("unexpected recovered state: %+v",recovered) }
}


func TestPeerV02ResourceBindingFailsClosed(t *testing.T) {
	dir:=t.TempDir()
	ledger,err:=NewFileOperationLedger(filepath.Join(dir,"operations.json"));if err!=nil{t.Fatal(err)}
	peer,err:=NewPeer("provider");if err!=nil{t.Fatal(err)}
	secret:=[]byte("0123456789abcdef0123456789abcdef")
	if err:=peer.AddCredential(Credential{
		KeyID:"caller-key",PeerID:"caller",PrincipalRef:"principal-a",Secret:secret,
		AllowedScopes:map[string]bool{"inventory.read":true},
		AllowedResources:map[string]bool{"project-a/source-a":true},
	});err!=nil{t.Fatal(err)}
	calls:=0
	p02,err:=NewPeerV02(peer,ledger);if err!=nil{t.Fatal(err)}
	if err:=p02.RegisterCapabilityWithResourceBinding("ecoscan.inventory.read","1.0",
		map[string]bool{"inventory.read":true},func(payload map[string]any)(map[string]any,error){
			calls++
			return map[string]any{"items_seen":1},nil
		},"IDEMPOTENT",true);err!=nil{t.Fatal(err)}
	message,signature:=testV02Message(t,secret,"resource-nonce","resource-attempt","resource-op","resource-idem","")
	message["capability"]=map[string]any{"id":"ecoscan.inventory.read","version":"1.0"}
	message["payload"]=map[string]any{"project_id":"project-b","source_id":"source-b"}
	hash,err:=OperationRequestHash(message);if err!=nil{t.Fatal(err)}
	message["operation"].(map[string]any)["request_hash"]=hash
	signature,err=Sign(message,secret);if err!=nil{t.Fatal(err)}
	_,_,protocolErr:=p02.Handle(message,"caller-key",signature)
	if protocolErr==nil||protocolErr.Code!="authorization.denied"{t.Fatalf("expected resource authorization denial, got %v",protocolErr)}
	if calls!=0{t.Fatalf("resource-denied request executed handler %d times",calls)}
}


func TestValidateV02StatusRequestWithResourceIdentity(t *testing.T) {
	now:=time.Now().Unix()
	raw:=[]byte(`{"protocol":"obis","version":"0.2","message_type":"operation_status_request","message_id":"status-message","nonce":"status-nonce","attempt_id":"status-attempt","sender":{"peer_id":"caller"},"recipient":{"peer_id":"provider"},"issued_at":`+fmtInt(now)+`,"expires_at":`+fmtInt(now+30)+`,"capability":{"id":"ecoscan.inventory.read","version":"1.0"},"authorization":{"principal_ref":"principal-a","scopes":["inventory.read"]},"operation_id":"operation-1","resource":{"project_id":"project-a","source_id":"source-a"}}`)
	message,err:=DecodeStrict(raw);if err!=nil{t.Fatal(err)}
	if protocolErr:=validateV02Message(message,time.Now());protocolErr!=nil{t.Fatalf("valid resource-scoped status request rejected: %+v",protocolErr)}
}


func TestIndependentBridexAndTradixOwnerIsolation(t *testing.T) {
	dir:=t.TempDir()
	bridexSecret:=[]byte("bridex-development-secret-32bytes")
	tradixSecret:=[]byte("tradix-development-secret-32bytes")
	bridexLedger,err:=NewFileOperationLedger(filepath.Join(dir,"bridex-operations.json"));if err!=nil{t.Fatal(err)}
	tradixLedger,err:=NewFileOperationLedger(filepath.Join(dir,"tradix-operations.json"));if err!=nil{t.Fatal(err)}
	bridexPeer,err:=NewPeer("peer:bridex");if err!=nil{t.Fatal(err)}
	tradixPeer,err:=NewPeer("peer:tradix");if err!=nil{t.Fatal(err)}
	if err=bridexPeer.AddCredential(Credential{KeyID:"bridex-key",PeerID:"caller",PrincipalRef:"principal:caller",Secret:bridexSecret,AllowedScopes:map[string]bool{"bridex:inventory:read":true},AllowedResources:map[string]bool{"project-a/source-a":true}});err!=nil{t.Fatal(err)}
	if err=tradixPeer.AddCredential(Credential{KeyID:"tradix-key",PeerID:"caller",PrincipalRef:"principal:caller",Secret:tradixSecret,AllowedScopes:map[string]bool{"tradix:tools:read":true},AllowedResources:map[string]bool{"project-b/source-b":true}});err!=nil{t.Fatal(err)}
	bridexCalls,tradixCalls:=0,0
	bridexV02,err:=NewPeerV02(bridexPeer,bridexLedger);if err!=nil{t.Fatal(err)}
	tradixV02,err:=NewPeerV02(tradixPeer,tradixLedger);if err!=nil{t.Fatal(err)}
	if err=bridexV02.RegisterCapabilityWithResourceBinding("bridex.inventory.read","1.0",map[string]bool{"bridex:inventory:read":true},func(map[string]any)(map[string]any,error){bridexCalls++;return map[string]any{"owner":"BRIDEX"},nil},"IDEMPOTENT",true);err!=nil{t.Fatal(err)}
	if err=tradixV02.RegisterCapabilityWithResourceBinding("tradix.tools.read","1.0",map[string]bool{"tradix:tools:read":true},func(map[string]any)(map[string]any,error){tradixCalls++;return map[string]any{"owner":"TRADIX"},nil},"IDEMPOTENT",true);err!=nil{t.Fatal(err)}

	build:=func(peerID,capability,scope,operationID,key string,secret []byte,projectID,sourceID,nonce string)(map[string]any,string){
		message,_:=testV02Message(t,secret,nonce,"attempt-"+nonce,operationID,"idem-"+operationID,"")
		message["recipient"]=map[string]any{"peer_id":peerID}
		message["capability"]=map[string]any{"id":capability,"version":"1.0"}
		message["authorization"]=map[string]any{"principal_ref":"principal:caller","scopes":[]any{scope}}
		message["payload"]=map[string]any{"project_id":projectID,"source_id":sourceID}
		hash,e:=OperationRequestHash(message);if e!=nil{t.Fatal(e)}
		message["operation"].(map[string]any)["request_hash"]=hash
		signature,e:=Sign(message,secret);if e!=nil{t.Fatal(e)}
		return message,signature
	}
	bridexMessage,bridexSignature:=build("peer:bridex","bridex.inventory.read","bridex:inventory:read","shared-op","bridex-key",bridexSecret,"project-a","source-a","bridex-nonce")
	tradixMessage,tradixSignature:=build("peer:tradix","tradix.tools.read","tradix:tools:read","shared-op","tradix-key",tradixSecret,"project-b","source-b","tradix-nonce")
	bridexResponse,_,e:=bridexV02.Handle(bridexMessage,"bridex-key",bridexSignature);if e!=nil{t.Fatalf("BRIDEX request rejected: %+v",e)}
	tradixResponse,_,e:=tradixV02.Handle(tradixMessage,"tradix-key",tradixSignature);if e!=nil{t.Fatalf("TRADIX request rejected: %+v",e)}
	if bridexResponse["operation"].(map[string]any)["result"].(map[string]any)["owner"]!="BRIDEX"{t.Fatal("BRIDEX returned another owner's result")}
	if tradixResponse["operation"].(map[string]any)["result"].(map[string]any)["owner"]!="TRADIX"{t.Fatal("TRADIX returned another owner's result")}
	if bridexCalls!=1||tradixCalls!=1{t.Fatalf("unexpected handler counts: BRIDEX=%d TRADIX=%d",bridexCalls,tradixCalls)}

	if _,_,e=bridexV02.Handle(tradixMessage,"tradix-key",tradixSignature);e==nil||e.Code!="identity.unknown_peer"{t.Fatalf("cross-owner credential accepted by BRIDEX: %+v",e)}
	deniedMessage,deniedSignature:=build("peer:bridex","bridex.inventory.read","bridex:inventory:read","denied-op","bridex-key",bridexSecret,"project-b","source-b","bridex-denied")
	if _,_,e=bridexV02.Handle(deniedMessage,"bridex-key",deniedSignature);e==nil||e.Code!="authorization.denied"{t.Fatalf("cross-project resource accepted by BRIDEX: %+v",e)}
	if bridexCalls!=1||tradixCalls!=1{t.Fatal("denied cross-owner/resource request executed a handler")}
	if _,ledgerErr:=bridexLedger.Get("shared-op","caller","principal:caller","bridex.inventory.read","1.0");ledgerErr!=nil{t.Fatalf("BRIDEX ledger missing own operation: %v",ledgerErr)}
	if _,ledgerErr:=tradixLedger.Get("shared-op","caller","principal:caller","tradix.tools.read","1.0");ledgerErr!=nil{t.Fatalf("TRADIX ledger missing own operation: %v",ledgerErr)}
	if _,ledgerErr:=bridexLedger.Get("shared-op","caller","principal:caller","tradix.tools.read","1.0");ledgerErr==nil{t.Fatal("BRIDEX ledger exposed TRADIX operation")}
}


func TestPeerV02StatusLookupIsBoundToOriginalResource(t *testing.T) {
	dir:=t.TempDir()
	ledger,err:=NewFileOperationLedger(filepath.Join(dir,"operations.json"));if err!=nil{t.Fatal(err)}
	peer,err:=NewPeer("provider");if err!=nil{t.Fatal(err)}
	secret:=[]byte("0123456789abcdef0123456789abcdef")
	if err:=peer.AddCredential(Credential{
		KeyID:"caller-key",PeerID:"caller",PrincipalRef:"principal-a",Secret:secret,
		AllowedScopes:map[string]bool{"inventory.read":true},
		AllowedResources:map[string]bool{"project-a/source-a":true,"project-b/source-b":true},
	});err!=nil{t.Fatal(err)}
	p02,err:=NewPeerV02(peer,ledger);if err!=nil{t.Fatal(err)}
	if err:=p02.RegisterCapabilityWithResourceBinding("ecoscan.inventory.read","1.0",
		map[string]bool{"inventory.read":true},func(payload map[string]any)(map[string]any,error){
			return map[string]any{"project_id":payload["project_id"],"source_id":payload["source_id"]},nil
		},"IDEMPOTENT",true);err!=nil{t.Fatal(err)}
	request,signature:=testV02Message(t,secret,"resource-status-nonce","resource-status-attempt","resource-status-op","resource-status-idem","")
	request["capability"]=map[string]any{"id":"ecoscan.inventory.read","version":"1.0"}
	request["authorization"]=map[string]any{"principal_ref":"principal-a","scopes":[]any{"inventory.read"}}
	request["payload"]=map[string]any{"project_id":"project-a","source_id":"source-a"}
	hash,err:=OperationRequestHash(request);if err!=nil{t.Fatal(err)}
	request["operation"].(map[string]any)["request_hash"]=hash
	signature,err=Sign(request,secret);if err!=nil{t.Fatal(err)}
	response,_,protocolErr:=p02.Handle(request,"caller-key",signature)
	if protocolErr!=nil{t.Fatal(protocolErr)}
	if response["operation"].(map[string]any)["state"]!="SUCCEEDED"{t.Fatal("operation did not succeed")}

	status:=map[string]any{
		"protocol":"obis","version":"0.2","message_type":"operation_status_request",
		"message_id":"status-resource-mismatch","nonce":"status-resource-nonce-2","attempt_id":"status-resource-attempt-2",
		"sender":map[string]any{"peer_id":"caller"},"recipient":map[string]any{"peer_id":"provider"},
		"issued_at":json.Number(fmtInt(time.Now().Unix())),"expires_at":json.Number(fmtInt(time.Now().Unix()+45)),
		"capability":map[string]any{"id":"ecoscan.inventory.read","version":"1.0"},
		"authorization":map[string]any{"principal_ref":"principal-a","scopes":[]any{"inventory.read"}},
		"operation_id":"resource-status-op",
		"resource":map[string]any{"project_id":"project-b","source_id":"source-b"},
	}
	statusSignature,err:=Sign(status,secret);if err!=nil{t.Fatal(err)}
	_,_,protocolErr=p02.Handle(status,"caller-key",statusSignature)
	if protocolErr==nil||protocolErr.Code!="operation.not_found"{t.Fatalf("expected resource-scoped not found, got %v",protocolErr)}
}
