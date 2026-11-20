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
	if len(os.Args)>1 && os.Args[1]=="invoke" {
		invoke(os.Args[2:])
		return
	}
	flags:=flag.NewFlagSet("obis-go-peer",flag.ExitOnError)
	peerID:=flags.String("peer-id","peer:go","local peer identifier")
	addr:=flags.String("listen","127.0.0.1:0","loopback listen address")
	keyID:=flags.String("key-id","go-dev-key","development credential key id")
	remoteID:=flags.String("remote-peer","peer:python","authenticated remote peer id")
	principal:=flags.String("principal","principal:python","authenticated principal")
	secretHex:=flags.String("secret-hex","","32-byte development secret in hex")
	scopesRaw:=flags.String("scopes","records:read","comma-separated granted scopes")
	_ = flags.Parse(os.Args[1:])
	secret,err:=hex.DecodeString(*secretHex);if err!=nil||len(secret)<32{log.Fatal("secret-hex must encode at least 32 bytes")}
	scopes:=map[string]bool{};for _,s:=range strings.Split(*scopesRaw,","){if s!=""{scopes[s]=true}}
	p,err:=obis.NewPeer(*peerID);if err!=nil{log.Fatal(err)}
	if err=p.AddCredential(obis.Credential{KeyID:*keyID,PeerID:*remoteID,PrincipalRef:*principal,Secret:secret,AllowedScopes:scopes});err!=nil{log.Fatal(err)}
	err=p.RegisterCapability(obis.Capability{ID:"records.read",Version:"1.0",RequiredScopes:map[string]bool{"records:read":true},Handler:func(payload map[string]any)(map[string]any,error){return map[string]any{"record_id":payload["record_id"],"served_by":"go-peer"},nil}})
	if err!=nil{log.Fatal(err)}
	listener,err:=obis.ListenLoopback(*addr,p.Handler());if err!=nil{log.Fatal(err)}
	fmt.Println(listener.Addr().String())
	if err=http.Serve(listener,p.Handler());err!=nil{log.Fatal(err)}
}

func invoke(args []string) {
	flags:=flag.NewFlagSet("obis-go-peer invoke",flag.ExitOnError)
	endpoint:=flags.String("endpoint","","bare loopback endpoint of the Python peer")
	local:=flags.String("local-peer","peer:go","local peer id")
	remote:=flags.String("remote-peer","peer:python","remote peer id")
	keyID:=flags.String("key-id","go-key","configured credential id")
	principal:=flags.String("principal","principal:go","configured principal")
	secretHex:=flags.String("secret-hex","","32-byte development secret in hex")
	scopesRaw:=flags.String("scopes","records:read","comma-separated requested scopes")
	capability:=flags.String("capability","records.read","capability id")
	version:=flags.String("capability-version","1.0","capability version")
	payloadRaw:=flags.String("payload",`{"record_id":"record-123"}`,"JSON object payload")
	_ = flags.Parse(args)
	secret,err:=hex.DecodeString(*secretHex);if err!=nil||len(secret)<32{log.Fatal("secret-hex must encode at least 32 bytes")}
	payload,err:=obis.DecodeStrict([]byte(*payloadRaw));if err!=nil{log.Fatal(err)}
	scopes:=strings.Split(*scopesRaw,",")
	response,err:=obis.Invoke(*endpoint,*local,*remote,*keyID,*principal,secret,scopes,*capability,*version,payload)
	if err!=nil{log.Fatal(err)}
	encoder:=json.NewEncoder(os.Stdout);encoder.SetEscapeHTML(false)
	if err=encoder.Encode(response);err!=nil{log.Fatal(err)}
}
