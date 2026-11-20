package obis

import (
	"net/http/httptest"
	"encoding/json"
	"path/filepath"
	"testing"
	"time"
)

func TestOBISV02LoopbackClientRoundTripAndStatus(t *testing.T) {
	dir:=t.TempDir()
	ledger,err:=NewFileOperationLedger(filepath.Join(dir,"operations.json"));if err!=nil{t.Fatal(err)}
	peer,err:=NewPeer("provider");if err!=nil{t.Fatal(err)}
	secret:=[]byte("0123456789abcdef0123456789abcdef")
	if err:=peer.AddCredential(Credential{KeyID:"caller-key",PeerID:"caller",PrincipalRef:"principal-a",Secret:secret,AllowedScopes:map[string]bool{"inventory.read":true}});err!=nil{t.Fatal(err)}
	executions:=0
	p02,err:=NewPeerV02(peer,ledger);if err!=nil{t.Fatal(err)}
	if err:=p02.RegisterCapability("ecoscan.inventory.read","1.0",map[string]bool{"inventory.read":true},func(payload map[string]any)(map[string]any,error){
		executions++
		return map[string]any{"items_seen":1,"source_id":payload["source_id"]},nil
	},"IDEMPOTENT");err!=nil{t.Fatal(err)}
	server:=httptest.NewServer(p02.HandlerV02());defer server.Close()
	result,err:=InvokeV02(server.URL,"caller","provider","caller-key","principal-a",secret,
		[]string{"inventory.read"},"ecoscan.inventory.read","1.0","op-ecoscan-1","idem-ecoscan-1",
		time.Now().Add(24*time.Hour),map[string]any{"project_id":"project-a","source_id":"source-a"})
	if err!=nil{t.Fatal(err)}
	if result.State!="SUCCEEDED"||executions!=1||result.Result["items_seen"]!=json.Number("1"){t.Fatalf("unexpected invocation result: %+v executions=%d",result,executions)}
	status,err:=GetOperationStatusV02(server.URL,"caller","provider","caller-key","principal-a",secret,
		[]string{"inventory.read"},"ecoscan.inventory.read","1.0","op-ecoscan-1")
	if err!=nil{t.Fatal(err)}
	if status.State!="SUCCEEDED"||executions!=1{t.Fatalf("status query changed execution count: %+v executions=%d",status,executions)}
}


func TestOBISV02ClientVerifiesSignedAuthorizationError(t *testing.T) {
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
	server:=httptest.NewServer(p02.HandlerV02());defer server.Close()
	_,err=InvokeV02(server.URL,"caller","provider","caller-key","principal-a",secret,
		[]string{"inventory.read"},"ecoscan.inventory.read","1.0","denied-op","denied-idem",
		time.Now().Add(24*time.Hour),map[string]any{"project_id":"project-b","source_id":"source-b"})
	var protocolErr *Error
	if !errors.As(err,&protocolErr){t.Fatalf("expected signed OBIS error, got %v",err)}
	if protocolErr.Code!="authorization.denied"||protocolErr.Status!=403{t.Fatalf("unexpected signed error: %+v",protocolErr)}
	if calls!=0{t.Fatalf("unauthorized handler ran %d times",calls)}
}
