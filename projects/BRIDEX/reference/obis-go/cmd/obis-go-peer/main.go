package main

import (
	"encoding/hex"
	"encoding/json"
	"flag"
	"fmt"
	"log"
	"net/http"
	"net"
	"time"
	"os"
	"strings"

	"github.com/grinlife4-stack/bridex-obis-go/obis"
)

func main() {
	args:=os.Args[1:]
	if len(args)>0 && args[0]=="server-v02" { serveV02(args[1:]); return }
	if len(args)>0 && args[0]=="invoke-v02" { invokeV02(args[1:]); return }
	if len(args)>0 && args[0]=="invoke" {
		invoke(args[1:])
		return
	}
	if len(args)>=2 && args[0]=="--mode" {
		mode:=args[1]
		args=args[2:]
		if mode=="invoke" { invoke(args); return }
		if mode!="server" { log.Fatalf("unsupported mode: %s",mode) }
	}
	flags:=flag.NewFlagSet("obis-go-peer",flag.ExitOnError)
	peerID:=flags.String("peer-id","peer:go","local peer identifier")
	addr:=flags.String("listen","127.0.0.1:0","loopback listen address")
	keyID:=flags.String("key-id","go-dev-key","development credential key id")
	remoteID:=flags.String("remote-peer","peer:python","authenticated remote peer id")
	principal:=flags.String("principal","principal:python","authenticated principal")
	secretHex:=flags.String("secret-hex","","32-byte development secret in hex")
	scopesRaw:=flags.String("scopes","records:read","comma-separated granted scopes")
	replayDir:=flags.String("replay-dir","","owner-controlled directory for durable nonce replay state; empty keeps in-memory mode")
	_ = flags.Parse(args)
	secret,err:=hex.DecodeString(*secretHex);if err!=nil||len(secret)<32{log.Fatal("secret-hex must encode at least 32 bytes")}
	scopes:=map[string]bool{};for _,s:=range strings.Split(*scopesRaw,","){if s!=""{scopes[s]=true}}
	p,err:=obis.NewPeer(*peerID);if err!=nil{log.Fatal(err)}
	if *replayDir!="" {
		guard,guardErr:=obis.NewFileReplayGuard(*replayDir);if guardErr!=nil{log.Fatalf("configure durable replay guard: %v",guardErr)}
		if guardErr=p.SetReplayGuard(guard);guardErr!=nil{log.Fatalf("install durable replay guard: %v",guardErr)}
	}
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
	peerID:=flags.String("peer-id","","alias for local peer id")
	remote:=flags.String("remote-peer","peer:python","remote peer id")
	keyID:=flags.String("key-id","go-key","configured credential id")
	principal:=flags.String("principal","principal:go","configured principal")
	secretHex:=flags.String("secret-hex","","32-byte development secret in hex")
	scopesRaw:=flags.String("scopes","records:read","comma-separated requested scopes")
	capability:=flags.String("capability","records.read","capability id")
	version:=flags.String("capability-version","1.0","capability version")
	payloadRaw:=flags.String("payload",`{"record_id":"record-123"}`,"JSON object payload")
	payloadJSON:=flags.String("payload-json","","alias for payload")
	_ = flags.Parse(args)
	secret,err:=hex.DecodeString(*secretHex);if err!=nil||len(secret)<32{log.Fatal("secret-hex must encode at least 32 bytes")}
	if *peerID!="" { *local=*peerID }
	if *payloadJSON!="" { *payloadRaw=*payloadJSON }
	payload,err:=obis.DecodeStrict([]byte(*payloadRaw));if err!=nil{log.Fatal(err)}
	scopes:=strings.Split(*scopesRaw,",")
	response,err:=obis.Invoke(*endpoint,*local,*remote,*keyID,*principal,secret,scopes,*capability,*version,payload)
	if err!=nil{log.Fatal(err)}
	encoder:=json.NewEncoder(os.Stdout);encoder.SetEscapeHTML(false)
	if err=encoder.Encode(response);err!=nil{log.Fatal(err)}
}

func serveV02(args []string) {
	flags:=flag.NewFlagSet("obis-go-peer server-v02",flag.ExitOnError)
	peerID:=flags.String("peer-id","peer:go-v02","local peer identifier")
	addr:=flags.String("listen","127.0.0.1:0","loopback listen address")
	keyID:=flags.String("key-id","python-dev-key","development credential key id")
	remoteID:=flags.String("remote-peer","peer:python","authenticated remote peer id")
	principal:=flags.String("principal","principal:python","authenticated principal")
	secretHex:=flags.String("secret-hex","","32-byte development secret in hex")
	scopesRaw:=flags.String("scopes","inventory.read","comma-separated granted scopes")
	ledgerPath:=flags.String("ledger-path","","persistent operation ledger path")
	replayDir:=flags.String("replay-dir","","owner-controlled durable replay directory")
	allowedResourcesRaw:=flags.String("allowed-resource","","comma-separated project/source resource grants")
	capabilityID:=flags.String("capability","ecoscan.inventory.read","registered capability ID")
	capabilityVersion:=flags.String("capability-version","1.0","registered capability version")
	_ = flags.Parse(args)
	secret,err:=hex.DecodeString(*secretHex);if err!=nil||len(secret)<32{log.Fatal("secret-hex must encode at least 32 bytes")}
	if *ledgerPath==""{log.Fatal("ledger-path is required")}
	scopes:=map[string]bool{};for _,scope:=range strings.Split(*scopesRaw,","){if scope!=""{scopes[scope]=true}}
	peer,err:=obis.NewPeer(*peerID);if err!=nil{log.Fatal(err)}
	allowedResources:=map[string]bool{};for _,pair:=range strings.Split(*allowedResourcesRaw,","){parts:=strings.SplitN(pair,"/",2);if len(parts)==2&&parts[0]!=""&&parts[1]!=""{allowedResources[parts[0]+"/"+parts[1]]=true}}
	if err=peer.AddCredential(obis.Credential{KeyID:*keyID,PeerID:*remoteID,PrincipalRef:*principal,Secret:secret,AllowedScopes:scopes,AllowedResources:allowedResources});err!=nil{log.Fatal(err)}
	if *replayDir!=""{
		guard,guardErr:=obis.NewFileReplayGuard(*replayDir);if guardErr!=nil{log.Fatalf("configure durable replay guard: %v",guardErr)}
		if guardErr=peer.SetReplayGuard(guard);guardErr!=nil{log.Fatal(guardErr)}
	}
	ledger,err:=obis.NewFileOperationLedger(*ledgerPath);if err!=nil{log.Fatal(err)}
	p02,err:=obis.NewPeerV02(peer,ledger);if err!=nil{log.Fatal(err)}
	err=p02.RegisterCapabilityWithResourceBinding(*capabilityID,*capabilityVersion,map[string]bool{"inventory.read":true},func(payload map[string]any)(map[string]any,error){
		rawKinds,_:=payload["measurement_kinds"].([]any)
		measurements:=map[string]any{}
		for _,raw:=range rawKinds {
			kind,ok:=raw.(string);if !ok{return nil,fmt.Errorf("invalid measurement kind")}
			switch kind {
			case "logical_bytes": measurements[kind]=int64(4096)
			case "file_count": measurements[kind]=int64(2)
			default: return nil,fmt.Errorf("unsupported measurement kind: %s",kind)
			}
		}
		return map[string]any{
			"project_id":payload["project_id"],"source_id":payload["source_id"],
			"coverage_state":"COMPLETE","items_seen":2,"pages_seen":1,
			"measurements":measurements,"source_timestamp":"2026-11-20T10:00:00Z",
			"limitations":[]any{},"evidence_ref":"test-evidence:go-peer-v02",
		},nil
	},"IDEMPOTENT",true)
	if err!=nil{log.Fatal(err)}
	host,_,err:=net.SplitHostPort(*addr);if err!=nil{log.Fatal(err)}
	ip:=net.ParseIP(host);if host!="localhost"&&(ip==nil||!ip.IsLoopback()){log.Fatal("OBIS 0.2 development server is loopback-only")}
	listener,err:=net.Listen("tcp",*addr);if err!=nil{log.Fatal(err)}
	fmt.Println(listener.Addr().String())
	server:=&http.Server{Handler:p02.HandlerV02(),ReadHeaderTimeout:2*time.Second,ReadTimeout:5*time.Second,WriteTimeout:5*time.Second,IdleTimeout:15*time.Second,MaxHeaderBytes:16*1024}
	if err=server.Serve(listener);err!=nil{log.Fatal(err)}
}

func invokeV02(args []string) {
	flags:=flag.NewFlagSet("obis-go-peer invoke-v02",flag.ExitOnError)
	endpoint:=flags.String("endpoint","","bare loopback endpoint of the OBIS 0.2 peer")
	local:=flags.String("local-peer","peer:go","local peer ID")
	remote:=flags.String("remote-peer","peer:python","remote peer ID")
	keyID:=flags.String("key-id","go-dev-key","configured credential key ID")
	principal:=flags.String("principal","principal:go","configured principal")
	secretHex:=flags.String("secret-hex","","32-byte development secret in hex")
	scopesRaw:=flags.String("scopes","inventory.read","comma-separated requested scopes")
	capability:=flags.String("capability","ecoscan.inventory.read","capability ID")
	version:=flags.String("capability-version","1.0","capability version")
	operationID:=flags.String("operation-id","go-operation-1","stable operation ID")
	idempotencyKey:=flags.String("idempotency-key","go-idem-1","stable idempotency key")
	payloadRaw:=flags.String("payload",`{"project_id":"project-a","source_id":"source-a"}`,"JSON object payload")
	_ = flags.Parse(args)
	secret,err:=hex.DecodeString(*secretHex);if err!=nil||len(secret)<32{log.Fatal("secret-hex must encode at least 32 bytes")}
	payload,err:=obis.DecodeStrict([]byte(*payloadRaw));if err!=nil{log.Fatal(err)}
	result,err:=obis.InvokeV02(*endpoint,*local,*remote,*keyID,*principal,secret,strings.Split(*scopesRaw,","),*capability,*version,*operationID,*idempotencyKey,time.Now().Add(24*time.Hour),payload)
	if err!=nil{log.Fatal(err)}
	encoder:=json.NewEncoder(os.Stdout);encoder.SetEscapeHTML(false)
	if err=encoder.Encode(result);err!=nil{log.Fatal(err)}
}
