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
