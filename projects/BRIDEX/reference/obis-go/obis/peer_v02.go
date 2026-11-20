package obis

import (
	"crypto/hmac"
	"errors"
	"fmt"
	"math"
	"sort"
	"time"
)

type OperationCapabilityV02 struct {
	ID string
	Version string
	RequiredScopes map[string]bool
	Handler CapabilityHandler
	RecoveryClass string
	ResourceBinding bool
}

type PeerV02 struct {
	Peer *Peer
	Ledger *FileOperationLedger
	capabilities map[string]OperationCapabilityV02
}

func NewPeerV02(peer *Peer, ledger *FileOperationLedger) (*PeerV02, error) {
	if peer == nil || ledger == nil { return nil, errors.New("OBIS 0.2 requires a peer and durable operation ledger") }
	if _, err := ledger.RecoverRunningAsUnknown(float64(time.Now().Unix())); err != nil { return nil, fmt.Errorf("recover operation ledger: %w", err) }
	return &PeerV02{Peer: peer, Ledger: ledger, capabilities: map[string]OperationCapabilityV02{}}, nil
}

func (p *PeerV02) RegisterCapability(id, version string, scopes map[string]bool, handler CapabilityHandler, recoveryClass string) error {
	return p.RegisterCapabilityWithResourceBinding(id,version,scopes,handler,recoveryClass,false)
}

func (p *PeerV02) RegisterCapabilityWithResourceBinding(id, version string, scopes map[string]bool, handler CapabilityHandler, recoveryClass string, resourceBinding bool) error {
	if id == "" || version == "" || handler == nil || len(scopes) == 0 { return errors.New("capability ID, version, handler, and required scopes are mandatory") }
	if recoveryClass != "IDEMPOTENT" && recoveryClass != "QUERYABLE" && recoveryClass != "NON_RECOVERABLE" { return errors.New("invalid capability recovery class") }
	key := id + "\x00" + version
	if _, exists := p.capabilities[key]; exists { return errors.New("duplicate OBIS 0.2 capability") }
	copyScopes := make(map[string]bool, len(scopes))
	for scope, allowed := range scopes { if scope == "" || !allowed { return errors.New("required scopes must be non-empty and true") }; copyScopes[scope] = true }
	p.capabilities[key] = OperationCapabilityV02{ID:id, Version:version, RequiredScopes:copyScopes, Handler:handler, RecoveryClass:recoveryClass, ResourceBinding:resourceBinding}
	return nil
}

func validateV02Message(m map[string]any, now time.Time) *Error {
	common := []string{"protocol","version","message_type","message_id","nonce","attempt_id","sender","recipient","issued_at","expires_at","capability","authorization"}
	messageType, _ := str(m, "message_type")
	required := append([]string(nil), common...)
	switch messageType {
	case "request": required = append(required, "operation", "payload")
	case "operation_status_request":
        required = append(required, "operation_id")
        if _, exists := m["resource"]; exists { required = append(required, "resource") }
	default: return &Error{"protocol.invalid_message","invalid OBIS 0.2 message_type",400}
	}
	if !exactKeys(m, required...) { return &Error{"protocol.invalid_message","unknown or missing OBIS 0.2 fields",400} }
	if m["protocol"] != "obis" || m["version"] != "0.2" { return &Error{"protocol.unsupported_version","unsupported protocol/version",426} }
	for _, field := range []string{"message_id","nonce","attempt_id"} {
		value, ok := str(m, field); if !ok || value == "" || len(value) > 200 { return &Error{"protocol.invalid_message","invalid "+field,400} }
	}
	for _, field := range []string{"sender","recipient"} {
		value, ok := obj(m, field); if !ok || !exactKeys(value,"peer_id") { return &Error{"protocol.invalid_message","invalid "+field,400} }
		peerID, ok := str(value,"peer_id"); if !ok || peerID == "" { return &Error{"protocol.invalid_message","invalid "+field+" peer_id",400} }
	}
	capability, ok := obj(m,"capability")
	if !ok || !exactKeys(capability,"id","version") { return &Error{"protocol.invalid_message","invalid capability",400} }
	for _, field := range []string{"id","version"} { value, ok := str(capability,field); if !ok || value == "" { return &Error{"protocol.invalid_message","invalid capability "+field,400} } }
	auth, ok := obj(m,"authorization")
	if !ok || !exactKeys(auth,"principal_ref","scopes") { return &Error{"protocol.invalid_message","invalid authorization",400} }
	principal, ok := str(auth,"principal_ref"); if !ok || principal == "" { return &Error{"protocol.invalid_message","invalid principal_ref",400} }
	scopes, ok := auth["scopes"].([]any); if !ok || len(scopes) == 0 { return &Error{"protocol.invalid_message","scopes must be non-empty",400} }
	seen := map[string]bool{}
	for _, raw := range scopes { scope, ok := raw.(string); if !ok || scope == "" || seen[scope] { return &Error{"protocol.invalid_message","scopes must be unique non-empty strings",400} }; seen[scope] = true }
	issued, ok1 := number(m,"issued_at"); expires, ok2 := number(m,"expires_at")
	if !ok1 || !ok2 || issued < 0 || expires <= issued || expires <= float64(now.Unix()) || issued > float64(now.Unix()+ClockSkewSeconds) || expires-issued > MaxTTLSeconds {
		return &Error{"request.expired","request expiry/TTL is invalid",408}
	}
	if messageType == "request" {
		payload, ok := obj(m,"payload"); if !ok { return &Error{"protocol.invalid_message","payload must be an object",400} }
		operation, ok := obj(m,"operation"); if !ok || !exactKeys(operation,"operation_id","idempotency_key","request_hash","expires_at") { return &Error{"protocol.invalid_message","invalid operation identity",400} }
		for _, field := range []string{"operation_id","idempotency_key"} { value, ok := str(operation,field); if !ok || value == "" || len(value)>200 { return &Error{"protocol.invalid_message","invalid operation "+field,400} } }
		hash, ok := str(operation,"request_hash"); if !ok || validateRequestHash(hash)!=nil { return &Error{"protocol.invalid_message","invalid operation request_hash",400} }
		opExpiry, ok := number(operation,"expires_at"); if !ok || opExpiry <= float64(now.Unix()) || opExpiry < expires { return &Error{"protocol.invalid_message","invalid operation expiry",400} }
		_ = payload
	} else {
		operationID, ok := str(m,"operation_id"); if !ok || operationID == "" { return &Error{"protocol.invalid_message","invalid operation_id",400} }
		if raw, exists := m["resource"]; exists {
			resource, ok := raw.(map[string]any)
			if !ok { return &Error{"protocol.invalid_message","resource identity must be an object",400} }
			if !exactKeys(resource,"project_id","source_id") { return &Error{"protocol.invalid_message","resource identity must contain exactly project_id and source_id",400} }
			projectID, ok1 := str(resource,"project_id"); sourceID, ok2 := str(resource,"source_id")
			if !ok1 || !ok2 || projectID == "" || sourceID == "" { return &Error{"protocol.invalid_message","resource identity values must be non-empty strings",400} }
		}
	}
	raw, err := CanonicalJSON(m); if err != nil || len(raw) > MaxMessageBytes { return &Error{"payload.too_large","message exceeds size limit",413} }
	return nil
}

func (p *PeerV02) authenticate(m map[string]any, keyID, signature string) (Credential, *Error) {
	p.Peer.mu.Lock(); credential, exists := p.Peer.credentials[keyID]; guard := p.Peer.replayGuard; p.Peer.mu.Unlock()
	if !exists { return Credential{}, &Error{"identity.unknown_peer","unknown credential",401} }
	if !Verify(m, credential.Secret, signature) { return Credential{}, &Error{"identity.authentication_failed","signature verification failed",401} }
	sender,_ := obj(m,"sender"); recipient,_ := obj(m,"recipient"); auth,_ := obj(m,"authorization")
	senderID,_ := str(sender,"peer_id"); recipientID,_ := str(recipient,"peer_id"); principal,_ := str(auth,"principal_ref")
	if senderID != credential.PeerID || recipientID != p.Peer.ID || principal != credential.PrincipalRef { return Credential{}, &Error{"identity.authentication_failed","peer/principal mismatch",401} }
	nonce,_ := str(m,"nonce"); replayKey := keyID+":"+nonce; now := time.Now()
	if guard == nil {
		p.Peer.mu.Lock()
		for key, until := range p.Peer.seen { if !until.After(now) { delete(p.Peer.seen,key) } }
		if _, ok := p.Peer.seen[replayKey]; ok { p.Peer.mu.Unlock(); return Credential{}, &Error{"request.replay_detected","duplicate nonce",409} }
		p.Peer.seen[replayKey] = now.Add(time.Duration(MaxTTLSeconds+ClockSkewSeconds)*time.Second)
		p.Peer.mu.Unlock()
	} else if err := guard.Accept(replayKey, now.Add(time.Duration(MaxTTLSeconds+ClockSkewSeconds)*time.Second)); err != nil {
		if errors.Is(err,ErrReplayDetected) { return Credential{}, &Error{"request.replay_detected","duplicate nonce",409} }
		return Credential{}, &Error{"replay.storage_unavailable","replay protection storage unavailable",503}
	}
	return credential,nil
}

func validResourceIdentifier(value string) bool {
	if len(value) == 0 || len(value) > 128 { return false }
	for index, char := range value {
		letter := char >= 'a' && char <= 'z' || char >= 'A' && char <= 'Z'
		digit := char >= '0' && char <= '9'
		if index == 0 {
			if !letter && !digit { return false }
		} else if !letter && !digit && char != '.' && char != '_' && char != ':' && char != '-' {
			return false
		}
	}
	return true
}

func (p *PeerV02) authorize(m map[string]any, credential Credential) (OperationCapabilityV02, *Error) {
	capMap,_ := obj(m,"capability"); id,_ := str(capMap,"id"); version,_ := str(capMap,"version")
	capability, ok := p.capabilities[id+"\x00"+version]
	if !ok { return OperationCapabilityV02{}, &Error{"capability.unknown","capability is not registered",404} }
	auth,_ := obj(m,"authorization"); rawScopes,_ := auth["scopes"].([]any)
	requested := map[string]bool{}
	for _, raw := range rawScopes { requested[raw.(string)] = true }
	for scope := range capability.RequiredScopes { if !requested[scope] || !credential.AllowedScopes[scope] { return OperationCapabilityV02{}, &Error{"authorization.denied","required scope is not granted",403} } }
	for scope := range requested { if !credential.AllowedScopes[scope] { return OperationCapabilityV02{}, &Error{"authorization.denied","requested scope exceeds credential grant",403} } }
	if capability.ResourceBinding {
		payload,ok:=obj(m,"payload")
        if !ok { payload,ok=obj(m,"resource") }
        if !ok { return OperationCapabilityV02{}, &Error{"authorization.denied","resource-bound capability requires resource identity",403} }
		projectID,ok1:=str(payload,"project_id"); sourceID,ok2:=str(payload,"source_id")
		if !ok1||!ok2||!validResourceIdentifier(projectID)||!validResourceIdentifier(sourceID)||!credential.AllowedResources[projectID+"/"+sourceID] { return OperationCapabilityV02{}, &Error{"authorization.denied","resource is outside credential grant",403} }
	}
	return capability,nil
}

func operationResponse(m map[string]any, peerID string, record OperationRecord) map[string]any {
	sender,_ := obj(m,"sender"); senderID,_ := str(sender,"peer_id")
	return map[string]any{
		"protocol":"obis","version":"0.2","message_type":"operation_response",
		"message_id":fmt.Sprintf("go-%d",time.Now().UnixNano()),"correlation_id":m["message_id"],
		"sender":map[string]any{"peer_id":peerID},"recipient":map[string]any{"peer_id":senderID},
		"issued_at":float64(time.Now().Unix()),
		"operation":map[string]any{
			"operation_id":record.OperationID,"request_hash":record.RequestHash,"state":record.State,
			"result":record.Result,"result_ref":nullableString(record.ResultRef),"failure_code":nullableString(record.FailureCode),
			"created_at":record.CreatedAt,"updated_at":record.UpdatedAt,"expires_at":record.ExpiresAt,
		},
	}
}
func nullableString(s string) any { if s == "" { return nil }; return s }

func operationResourceRef(m map[string]any, capability OperationCapabilityV02) string {
	if !capability.ResourceBinding { return "" }
	resource,ok:=obj(m,"payload")
	if !ok { resource,_=obj(m,"resource") }
	projectID,_:=str(resource,"project_id")
	sourceID,_:=str(resource,"source_id")
	return projectID+"/"+sourceID
}

func (p *PeerV02) Handle(m map[string]any, keyID, signature string) (map[string]any, []byte, *Error) {
	if e := validateV02Message(m,time.Now()); e != nil { return nil,nil,e }
	credential,e := p.authenticate(m,keyID,signature); if e != nil { return nil,nil,e }
	capability,e := p.authorize(m,credential); if e != nil { return nil,credential.Secret,e }
	messageType,_ := str(m,"message_type")
	if messageType == "operation_status_request" {
		operationID,_ := str(m,"operation_id")
		resourceRef:=operationResourceRef(m,capability)
		record,err := p.Ledger.GetForResource(operationID,credential.PeerID,credential.PrincipalRef,capability.ID,capability.Version,resourceRef)
		if err != nil { return nil,credential.Secret,&Error{"operation.not_found","operation not found",404} }
		return operationResponse(m,p.Peer.ID,record),credential.Secret,nil
	}
	expectedHash,err := OperationRequestHash(m)
	if err != nil { return nil,nil,&Error{"operation.request_hash_mismatch","cannot compute request hash",400} }
	operation,_ := obj(m,"operation"); supplied,_ := str(operation,"request_hash")
	if !hmac.Equal([]byte(expectedHash),[]byte(supplied)) { return nil,nil,&Error{"operation.request_hash_mismatch","request hash verification failed",400} }
	idem,_ := str(operation,"idempotency_key"); idemHash,err := p.Ledger.IdempotencyKeyHash(idem)
	if err != nil { return nil,nil,&Error{"protocol.invalid_message","invalid idempotency key",400} }
	opID,_ := str(operation,"operation_id"); opExpiry,_ := number(operation,"expires_at")
	record,created,err := p.Ledger.Reserve(OperationRecord{
		OperationID:opID,PeerID:credential.PeerID,PrincipalRef:credential.PrincipalRef,
		CapabilityID:capability.ID,CapabilityVersion:capability.Version,
		IdempotencyKeyHash:idemHash,RequestHash:expectedHash,ResourceRef:operationResourceRef(m,capability),ExpiresAt:opExpiry,
	},float64(time.Now().Unix()))
	if errors.Is(err,ErrIdempotencyConflict) { return nil,nil,&Error{"operation.idempotency_conflict","idempotency identity conflicts with an existing operation",409} }
	if err != nil { return nil,nil,&Error{"operation.ledger_unavailable","operation ledger unavailable",503} }
	if created || record.State == "ACCEPTED" {
		record,err = p.Ledger.Transition(opID,"RUNNING",float64(time.Now().Unix()),nil,"","")
		if err != nil { return nil,nil,&Error{"operation.ledger_unavailable","operation could not enter RUNNING",503} }
		payload,_ := obj(m,"payload")
		result,handlerErr := capability.Handler(payload)
		if handlerErr != nil || result == nil {
			record,err = p.Ledger.Transition(opID,"UNKNOWN",float64(time.Now().Unix()),nil,"","operation.outcome_unknown")
		} else {
			if _,marshalErr := CanonicalJCSValue(result); marshalErr != nil { handlerErr = marshalErr }
			if handlerErr != nil { record,err = p.Ledger.Transition(opID,"UNKNOWN",float64(time.Now().Unix()),nil,"","operation.outcome_unknown")
			} else { record,err = p.Ledger.Transition(opID,"SUCCEEDED",float64(time.Now().Unix()),result,"","") }
		}
		if err != nil { return nil,nil,&Error{"operation.ledger_unavailable","operation result could not be committed",503} }
	}
	return operationResponse(m,p.Peer.ID,record),credential.Secret,nil
}

func sortV02Scopes(scopes []any) {
	sort.Slice(scopes,func(i,j int) bool { a,_:=scopes[i].(string); b,_:=scopes[j].(string); return a < b })
}

var _ = math.MaxFloat64
