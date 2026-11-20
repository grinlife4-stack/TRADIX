// Package obis is an independent Go implementation of the OBIS 0.1
// development transport. HMAC is for local conformance only, never production.
package obis

import (
	"bytes"
	"crypto/hmac"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"math"
	"net"
	"net/http"
	"sort"
	"strings"
	"sync"
	"time"
)

const (
	Protocol = "obis"
	Version = "0.1"
	MessagePath = "/obis/v0.1/messages"
	MaxMessageBytes = 64 * 1024
	MaxTTLSeconds = 60
	ClockSkewSeconds = 30
)

type Error struct { Code string; Message string; Status int }
func (e *Error) Error() string { return e.Code + ": " + e.Message }

type Credential struct {
	KeyID string
	PeerID string
	PrincipalRef string
	Secret []byte
	AllowedScopes map[string]bool
}

type CapabilityHandler func(map[string]any) (map[string]any, error)
type Capability struct {
	ID string
	Version string
	RequiredScopes map[string]bool
	Handler CapabilityHandler
}

type Peer struct {
	ID string
	mu sync.Mutex
	credentials map[string]Credential
	capabilities map[string]Capability
	seen map[string]time.Time
}

func NewPeer(id string) (*Peer, error) {
	if strings.TrimSpace(id) == "" { return nil, errors.New("peer id is required") }
	return &Peer{ID:id, credentials:map[string]Credential{}, capabilities:map[string]Capability{}, seen:map[string]time.Time{}}, nil
}
func (p *Peer) AddCredential(c Credential) error {
	if c.KeyID == "" || c.PeerID == "" || c.PrincipalRef == "" || len(c.Secret) < 32 || len(c.AllowedScopes)==0 { return errors.New("credential requires identifiers, 32-byte secret, and explicit scopes") }
	p.mu.Lock(); defer p.mu.Unlock()
	if _,ok:=p.credentials[c.KeyID]; ok { return errors.New("duplicate key id") }
	p.credentials[c.KeyID]=c; return nil
}
func (p *Peer) RegisterCapability(c Capability) error {
	if c.ID=="" || c.Version=="" || c.Handler==nil || len(c.RequiredScopes)==0 { return errors.New("capability requires id, version, handler, and explicit scopes") }
	p.mu.Lock(); defer p.mu.Unlock()
	key:=c.ID+"\x00"+c.Version
	if _,ok:=p.capabilities[key]; ok { return errors.New("duplicate capability") }
	p.capabilities[key]=c; return nil
}

// DecodeStrict rejects duplicate JSON object keys and trailing JSON values.
func DecodeStrict(raw []byte) (map[string]any,error) {
	dec:=json.NewDecoder(bytes.NewReader(raw)); dec.UseNumber()
	value,err:=decodeValue(dec); if err!=nil{return nil,err}
	if _,err=dec.Token(); err!=io.EOF { if err==nil{return nil,errors.New("trailing JSON value")}; return nil,err }
	obj,ok:=value.(map[string]any); if !ok{return nil,errors.New("message must be an object")}
	return obj,nil
}
func decodeValue(dec *json.Decoder)(any,error){
	t,err:=dec.Token(); if err!=nil{return nil,err}
	switch v:=t.(type){
	case json.Delim:
		switch v {
		case '{':
			m:=map[string]any{}
			for dec.More(){ keyToken,e:=dec.Token(); if e!=nil{return nil,e}; key,ok:=keyToken.(string); if !ok{return nil,errors.New("object key must be string")}; if _,exists:=m[key];exists{return nil,fmt.Errorf("duplicate JSON key: %s",key)}; val,e:=decodeValue(dec); if e!=nil{return nil,e}; m[key]=val }
			_,err=dec.Token(); return m,err
		case '[':
			a:=[]any{}; for dec.More(){val,e:=decodeValue(dec);if e!=nil{return nil,e};a=append(a,val)}; _,err=dec.Token();return a,err
		}
	case json.Number,string,bool,nil:
		return v,nil
	}
	return nil,errors.New("invalid JSON token")
}

// CanonicalJSON matches the Python development prototype for ordinary JSON
// values used by the conformance profile. Production signing canonicalization
// is deliberately not specified by this function.
func CanonicalJSON(v any)([]byte,error){
	var b bytes.Buffer
	enc:=json.NewEncoder(&b); enc.SetEscapeHTML(false)
	if err:=enc.Encode(v);err!=nil{return nil,err}
	return bytes.TrimSuffix(b.Bytes(),[]byte("\n")),nil
}
func Sign(v any, secret []byte)(string,error){
	raw,err:=CanonicalJSON(v);if err!=nil{return "",err}
	mac:=hmac.New(sha256.New,secret);mac.Write(raw);return hex.EncodeToString(mac.Sum(nil)),nil
}
func Verify(v any,secret []byte,sig string)bool{
	got,err:=hex.DecodeString(sig);if err!=nil{return false}
	raw,err:=CanonicalJSON(v);if err!=nil{return false}
	mac:=hmac.New(sha256.New,secret);mac.Write(raw)
	return hmac.Equal(got,mac.Sum(nil))
}
func str(m map[string]any,k string)(string,bool){v,ok:=m[k].(string);return v,ok}
func obj(m map[string]any,k string)(map[string]any,bool){v,ok:=m[k].(map[string]any);return v,ok}
func number(m map[string]any,k string)(float64,bool){
	v,ok:=m[k].(json.Number);if !ok{return 0,false}; n,e:=v.Float64();return n,e==nil&&!math.IsNaN(n)&&!math.IsInf(n,0)
}
func exactKeys(m map[string]any, keys ...string)bool{
	if len(m)!=len(keys){return false}; for _,k:=range keys{if _,ok:=m[k];!ok{return false}};return true
}
func ValidateRequest(m map[string]any, now time.Time) *Error {
	keys:=[]string{"protocol","version","message_type","message_id","nonce","sender","recipient","issued_at","expires_at","capability","authorization","payload"}
	if !exactKeys(m,keys...){return &Error{"protocol.invalid_message","unknown or missing request fields",400}}
	for k,want:=range map[string]string{"protocol":Protocol,"version":Version,"message_type":"request"}{v,_:=str(m,k);if v!=want{return &Error{"protocol.unsupported_version","unsupported protocol/version",426}}}
	for _,k:=range []string{"message_id","nonce"}{v,ok:=str(m,k);if !ok||v==""||len(v)>200{return &Error{"protocol.invalid_message","invalid "+k,400}}}
	sender,ok1:=obj(m,"sender");recipient,ok2:=obj(m,"recipient");auth,ok3:=obj(m,"authorization");capability,ok4:=obj(m,"capability");payload,ok5:=obj(m,"payload")
	if !ok1||!ok2||!ok3||!ok4||!ok5||!exactKeys(sender,"peer_id")||!exactKeys(recipient,"peer_id")||!exactKeys(auth,"principal_ref","scopes")||!exactKeys(capability,"id","version"){return &Error{"protocol.invalid_message","invalid nested request object",400}}
	for _,pair:=range []struct{m map[string]any;k string}{{sender,"peer_id"},{recipient,"peer_id"},{auth,"principal_ref"},{capability,"id"},{capability,"version"}}{v,ok:=str(pair.m,pair.k);if !ok||v==""{return &Error{"protocol.invalid_message","invalid nested string field",400}}}
	scopes,ok:=auth["scopes"].([]any);if !ok||len(scopes)==0{return &Error{"protocol.invalid_message","authorization scopes must be non-empty",400}}
	seen:=map[string]bool{};for _,raw:=range scopes{s,ok:=raw.(string);if !ok||s==""||seen[s]{return &Error{"protocol.invalid_message","authorization scopes must be unique strings",400}};seen[s]=true}
	issued,ok1:=number(m,"issued_at");expires,ok2:=number(m,"expires_at");if !ok1||!ok2||issued<0||expires<0{return &Error{"protocol.invalid_message","timestamps must be finite non-negative numbers",400}}
	n:=float64(now.Unix());if issued>n+ClockSkewSeconds||expires<=n||expires<=issued||expires-issued>MaxTTLSeconds{return &Error{"request.expired","request expiry/TTL is invalid",408}}
	raw,err:=CanonicalJSON(m);if err!=nil||len(raw)>MaxMessageBytes{return &Error{"payload.too_large","message exceeds size limit",413}}
	return nil
}
func (p *Peer) Handle(m map[string]any,keyID,sig string)(map[string]any,string,*Error){
	if e:=ValidateRequest(m,time.Now());e!=nil{return nil,"",e}
	p.mu.Lock();cred,ok:=p.credentials[keyID];p.mu.Unlock()
	if !ok{return nil,"",&Error{"identity.unknown_peer","unknown credential",401}}
	if !Verify(m,cred.Secret,sig){return nil,"",&Error{"identity.authentication_failed","signature verification failed",401}}
	sender,_:=obj(m,"sender");recipient,_:=obj(m,"recipient");auth,_:=obj(m,"authorization")
	senderID,_:=str(sender,"peer_id");recipientID,_:=str(recipient,"peer_id");principal,_:=str(auth,"principal_ref")
	if senderID!=cred.PeerID||recipientID!=p.ID||principal!=cred.PrincipalRef{return nil,"",&Error{"identity.authentication_failed","peer/principal mismatch",401}}
	nonce,_:=str(m,"nonce"); replayKey:=keyID+":"+nonce
	p.mu.Lock()
	now:=time.Now();for k,until:=range p.seen{if !until.After(now){delete(p.seen,k)}}
	if _,exists:=p.seen[replayKey];exists{p.mu.Unlock();return nil,"",&Error{"request.replay_detected","duplicate nonce",409}}
	p.seen[replayKey]=now.Add(time.Duration(MaxTTLSeconds+ClockSkewSeconds)*time.Second)
	capMap,_:=obj(m,"capability");capID,_:=str(capMap,"id");capVersion,_:=str(capMap,"version");cap,exists:=p.capabilities[capID+"\x00"+capVersion]
	p.mu.Unlock()
	if !exists{return nil,"",&Error{"capability.unknown","capability is not registered",404}}
	requested:=map[string]bool{};rawScopes,_:=auth["scopes"].([]any);for _,s:=range rawScopes{requested[s.(string)]=true}
	for scope:=range cap.RequiredScopes{if !requested[scope]||!cred.AllowedScopes[scope]{return nil,"",&Error{"authorization.denied","required scope is not granted",403}}}
	for scope:=range requested{if !cred.AllowedScopes[scope]{return nil,"",&Error{"authorization.denied","requested scope exceeds grant",403}}}
	payload,_:=obj(m,"payload");result,err:=cap.Handler(payload);if err!=nil{return nil,"",&Error{"operation.failed","capability execution failed",500}}
	response:=map[string]any{"protocol":Protocol,"version":Version,"message_type":"response","message_id":fmt.Sprintf("go-%d",time.Now().UnixNano()),"correlation_id":m["message_id"],"sender":map[string]any{"peer_id":p.ID},"recipient":map[string]any{"peer_id":senderID},"issued_at":float64(time.Now().Unix()),"outcome":"succeeded","result":result}
	return response,hex.EncodeToString(cred.Secret),nil
}
func (p *Peer) Handler() http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter,r *http.Request){
		if r.Method!="POST"||r.URL.Path!=MessagePath{http.NotFound(w,r);return}
		if r.Header.Get("Content-Type")!="application/obis+json"{http.Error(w,"unsupported content type",415);return}
		if r.Header.Get("Transfer-Encoding")!=""{http.Error(w,"transfer encoding unsupported",400);return}
		r.Body=http.MaxBytesReader(w,r.Body,MaxMessageBytes)
		raw,err:=io.ReadAll(r.Body);if err!=nil||len(raw)==0{http.Error(w,"invalid body",413);return}
		m,err:=DecodeStrict(raw);if err!=nil{http.Error(w,"invalid JSON",400);return}
		response,secretHex,protocolErr:=p.Handle(m,r.Header.Get("X-OBIS-Key-Id"),r.Header.Get("X-OBIS-Signature"))
		if protocolErr!=nil{http.Error(w,protocolErr.Error(),protocolErr.Status);return}
		secret,_:=hex.DecodeString(secretHex);body,err:=CanonicalJSON(response);if err!=nil{http.Error(w,"internal error",500);return}
		sig,_:=Sign(response,secret);w.Header().Set("Content-Type","application/obis+json");w.Header().Set("X-OBIS-Signature",sig);w.WriteHeader(200);_,_=w.Write(body)
	})
}
func ListenLoopback(addr string,h http.Handler)(net.Listener,error){
	host,_,err:=net.SplitHostPort(addr);if err!=nil{return nil,err}
	ip:=net.ParseIP(host);if host!="localhost"&&(ip==nil||!ip.IsLoopback()){return nil,errors.New("development peer is loopback-only")}
	return net.Listen("tcp",addr)
}
func SortedKeys(m map[string]any)[]string{keys:=make([]string,0,len(m));for k:=range m{keys=append(keys,k)};sort.Strings(keys);return keys}
