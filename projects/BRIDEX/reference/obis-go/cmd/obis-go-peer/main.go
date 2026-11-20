package main

import (
	"encoding/hex"
	"encoding/json"
	"flag"
	"fmt"
	"log"
	"net/http"
	"os"
	"strings"

	"github.com/grinlife4-stack/bridex-obis-go/obis"
)

func main() {
	peerID:=flag.String("peer-id","peer:go","local peer identifier")
	addr:=flag.String("listen","127.0.0.1:0","loopback listen address")
	keyID:=flag.String("key-id","go-dev-key","development credential key id")
	remoteID:=flag.String("remote-peer","peer:python","authenticated remote peer id")
	principal:=flag.String("principal","principal:python","authenticated principal")
	secretHex:=flag.String("secret-hex","","32-byte development secret in hex")
	scopesRaw:=flag.String("scopes","records:read","comma-separated granted scopes")
	flag.Parse()
	secret,err:=hex.DecodeString(*secretHex);if err!=nil||len(secret)<32{log.Fatal("secret-hex must encode at least 32 bytes")}
	scopes:=map[string]bool{};for _,s:=range strings.Split(*scopesRaw,","){if s!=""{scopes[s]=true}}
	p,err:=obis.NewPeer(*peerID);if err!=nil{log.Fatal(err)}
	if err=p.AddCredential(obis.Credential{KeyID:*keyID,PeerID:*remoteID,PrincipalRef:*principal,Secret:secret,AllowedScopes:scopes});err!=nil{log.Fatal(err)}
	err=p.RegisterCapability(obis.Capability{ID:"records.read",Version:"1.0",RequiredScopes:map[string]bool{"records:read":true},Handler:func(payload map[string]any)(map[string]any,error){return map[string]any{"record_id":payload["record_id"],"served_by":"go-peer"},nil}})
	if err!=nil{log.Fatal(err)}
	listener,err:=obis.ListenLoopback(*addr,p.Handler());if err!=nil{log.Fatal(err)}
	fmt.Println(listener.Addr().String())
	if err=http.Serve(listener,p.Handler());err!=nil{log.Fatal(err)}
	_ = os.Stdout
}
