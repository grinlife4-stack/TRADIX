package obis

import (
	"bytes"
	"crypto/rand"
	"encoding/hex"
	"errors"
	"io"
	"net"
	"net/http"
	"net/url"
	"math"
	"sort"
	"strconv"
	"strings"
	"time"
)

type OperationResultV02 struct {
	OperationID string `json:"operation_id"`
	RequestHash string `json:"request_hash"`
	State string `json:"state"`
	Result map[string]any `json:"result"`
	ResultRef *string `json:"result_ref"`
	FailureCode *string `json:"failure_code"`
	CreatedAt float64 `json:"created_at"`
	UpdatedAt float64 `json:"updated_at"`
	ExpiresAt float64 `json:"expires_at"`
}

func randomHexV02(size int) (string,error) {
	raw:=make([]byte,size)
	if _,err:=rand.Read(raw);err!=nil{return "",err}
	return hex.EncodeToString(raw),nil
}

func validateLoopbackEndpointV02(endpoint string) error {
	u,err:=url.Parse(endpoint);if err!=nil{return err}
	ip:=net.ParseIP(u.Hostname())
	if u.Scheme!="http"||u.User!=nil||u.RawQuery!=""||u.Fragment!=""||(u.Path!=""&&u.Path!="/")||
		(u.Hostname()!="localhost"&&(ip==nil||!ip.IsLoopback())) {
		return errors.New("OBIS 0.2 development client accepts only a bare loopback HTTP endpoint")
	}
	if _,_,err:=net.SplitHostPort(u.Host);err!=nil{return errors.New("OBIS 0.2 endpoint must include a port")}
	return nil
}

func InvokeV02(endpoint,localPeerID,remotePeerID,keyID,principal string,secret []byte,scopes []string,
	capabilityID,capabilityVersion,operationID,idempotencyKey string,operationExpiry time.Time,payload map[string]any) (OperationResultV02,error) {
	if localPeerID==""||remotePeerID==""||keyID==""||principal==""||len(secret)<32||len(scopes)==0||
		capabilityID==""||capabilityVersion==""||operationID==""||idempotencyKey==""||payload==nil {
		return OperationResultV02{},errors.New("OBIS 0.2 peer, identity, scope, capability, operation and payload fields are required")
	}
	if err:=validateLoopbackEndpointV02(endpoint);err!=nil{return OperationResultV02{},err}
	now:=time.Now()
	if !operationExpiry.After(now.Add(time.Duration(MaxTTLSeconds)*time.Second)){return OperationResultV02{},errors.New("operation expiry must exceed message expiry")}
	normalized:=append([]string(nil),scopes...);sort.Strings(normalized)
	scopeValues:=make([]any,len(normalized))
	for i,s:=range normalized {if s==""||(i>0&&s==normalized[i-1]){return OperationResultV02{},errors.New("scopes must be unique non-empty strings")};scopeValues[i]=s}
	messageID,err:=randomHexV02(18);if err!=nil{return OperationResultV02{},err}
	nonce,err:=randomHexV02(24);if err!=nil{return OperationResultV02{},err}
	attempt,err:=randomHexV02(18);if err!=nil{return OperationResultV02{},err}
	issued:=now.Unix()
	message:=map[string]any{
		"protocol":"obis","version":"0.2","message_type":"request",
		"message_id":messageID,"nonce":nonce,"attempt_id":attempt,
		"sender":map[string]any{"peer_id":localPeerID},"recipient":map[string]any{"peer_id":remotePeerID},
		"issued_at":issued,"expires_at":issued+MaxTTLSeconds,
		"capability":map[string]any{"id":capabilityID,"version":capabilityVersion},
		"authorization":map[string]any{"principal_ref":principal,"scopes":scopeValues},
		"operation":map[string]any{"operation_id":operationID,"idempotency_key":idempotencyKey,"request_hash":"","expires_at":float64(operationExpiry.Unix())},
		"payload":payload,
	}
	hash,err:=OperationRequestHash(message);if err!=nil{return OperationResultV02{},err}
	message["operation"].(map[string]any)["request_hash"]=hash
	return sendV02(endpoint,localPeerID,remotePeerID,keyID,secret,message,operationID,hash)
}

func GetOperationStatusV02(endpoint,localPeerID,remotePeerID,keyID,principal string,secret []byte,scopes []string,
	capabilityID,capabilityVersion,operationID string, resource ...map[string]any) (OperationResultV02,error) {
	if localPeerID==""||remotePeerID==""||keyID==""||principal==""||len(secret)<32||len(scopes)==0||capabilityID==""||capabilityVersion==""||operationID=="" {
		return OperationResultV02{},errors.New("OBIS 0.2 status query identity and operation fields are required")
	}
	if err:=validateLoopbackEndpointV02(endpoint);err!=nil{return OperationResultV02{},err}
	normalized:=append([]string(nil),scopes...);sort.Strings(normalized);scopeValues:=make([]any,len(normalized))
	for i,s:=range normalized {if s==""||(i>0&&s==normalized[i-1]){return OperationResultV02{},errors.New("scopes must be unique non-empty strings")};scopeValues[i]=s}
	now:=time.Now().Unix();messageID,err:=randomHexV02(18);if err!=nil{return OperationResultV02{},err}
	nonce,err:=randomHexV02(24);if err!=nil{return OperationResultV02{},err}
	attempt,err:=randomHexV02(18);if err!=nil{return OperationResultV02{},err}
	message:=map[string]any{
		"protocol":"obis","version":"0.2","message_type":"operation_status_request",
		"message_id":messageID,"nonce":nonce,"attempt_id":attempt,
		"sender":map[string]any{"peer_id":localPeerID},"recipient":map[string]any{"peer_id":remotePeerID},
		"issued_at":now,"expires_at":now+MaxTTLSeconds,
		"capability":map[string]any{"id":capabilityID,"version":capabilityVersion},
		"authorization":map[string]any{"principal_ref":principal,"scopes":scopeValues},
		"operation_id":operationID,
	}
	if len(resource)>1 { return OperationResultV02{},errors.New("at most one resource identity may be supplied") }
	if len(resource)==1 {
		if len(resource[0])!=2 || resource[0]["project_id"]==nil || resource[0]["source_id"]==nil {
			return OperationResultV02{},errors.New("resource identity requires project_id and source_id")
		}
		message["resource"]=resource[0]
	}
	return sendV02(endpoint,localPeerID,remotePeerID,keyID,secret,message,operationID,"")
}

func sendV02(endpoint,localPeerID,remotePeerID,keyID string,secret []byte,message map[string]any,operationID,expectedHash string)(OperationResultV02,error) {
	body,err:=CanonicalJSON(message);if err!=nil{return OperationResultV02{},err}
	signature,err:=Sign(message,secret);if err!=nil{return OperationResultV02{},err}
	request,err:=http.NewRequest(http.MethodPost,strings.TrimRight(endpoint,"/")+MessagePathV02,bytes.NewReader(body));if err!=nil{return OperationResultV02{},err}
	request.Header.Set("Content-Type","application/obis+json")
	request.Header.Set("X-OBIS-Key-Id",keyID)
	request.Header.Set("X-OBIS-Signature",signature)
	client:=&http.Client{Timeout:3*time.Second,CheckRedirect:func(*http.Request,[]*http.Request)error{return http.ErrUseLastResponse}}
	response,err:=client.Do(request);if err!=nil{return OperationResultV02{},classifyTransportError(err)}
	defer response.Body.Close()
	raw,err:=io.ReadAll(io.LimitReader(response.Body,MaxMessageBytes+1));if err!=nil{return OperationResultV02{},classifyTransportError(err)}
	if len(raw)==0||len(raw)>MaxMessageBytes{return OperationResultV02{},errors.New("OBIS 0.2 response size invalid")}
	if response.Header.Get("Content-Type")!="application/obis+json"{return OperationResultV02{},errors.New("unexpected OBIS 0.2 response content type")}
	if response.StatusCode!=http.StatusOK {
		responseSignature:=response.Header.Get("X-OBIS-Signature")
		if responseSignature!="" {
			errorMessage,decodeErr:=DecodeStrict(raw)
			if decodeErr!=nil||!Verify(errorMessage,secret,responseSignature) {
				return OperationResultV02{},errors.New("OBIS 0.2 signed error response verification failed")
			}
			if !exactKeys(errorMessage,"protocol","version","message_type","message_id","correlation_id","sender","recipient","issued_at","error")||
				errorMessage["protocol"]!="obis"||errorMessage["version"]!="0.2"||errorMessage["message_type"]!="error_response" {
				return OperationResultV02{},errors.New("invalid OBIS 0.2 signed error envelope")
			}
			correlation,_:=str(errorMessage,"correlation_id")
			if correlation!=message["message_id"] { return OperationResultV02{},errors.New("OBIS 0.2 signed error correlation mismatch") }
			sender,_:=obj(errorMessage,"sender");recipient,_:=obj(errorMessage,"recipient")
			senderID,_:=str(sender,"peer_id");recipientID,_:=str(recipient,"peer_id")
			if senderID!=remotePeerID||recipientID!=localPeerID { return OperationResultV02{},errors.New("OBIS 0.2 signed error peer identity mismatch") }
			errorFields,ok:=obj(errorMessage,"error")
			if !ok||!exactKeys(errorFields,"code","message") { return OperationResultV02{},errors.New("invalid OBIS 0.2 signed error details") }
			code,ok1:=str(errorFields,"code");detail,ok2:=str(errorFields,"message")
			if !ok1||!ok2||code==""||detail=="" { return OperationResultV02{},errors.New("invalid OBIS 0.2 signed error code/message") }
			return OperationResultV02{},&Error{Code:code,Message:detail,Status:response.StatusCode}
		}
		return OperationResultV02{},&Error{Code:"transport.remote_error",Message:"remote OBIS 0.2 request rejected with HTTP "+strconv.Itoa(response.StatusCode),Status:response.StatusCode}
	}
	resultMessage,err:=DecodeStrict(raw);if err!=nil{return OperationResultV02{},err}
	if !Verify(resultMessage,secret,response.Header.Get("X-OBIS-Signature")){return OperationResultV02{},errors.New("OBIS 0.2 response signature verification failed")}
	if !exactKeys(resultMessage,"protocol","version","message_type","message_id","correlation_id","sender","recipient","issued_at","operation")||
		resultMessage["protocol"]!="obis"||resultMessage["version"]!="0.2"||resultMessage["message_type"]!="operation_response" {
		return OperationResultV02{},errors.New("invalid OBIS 0.2 operation response envelope")
	}
	correlation,_:=str(resultMessage,"correlation_id");if correlation!=message["message_id"]{return OperationResultV02{},errors.New("OBIS 0.2 response correlation mismatch")}
	sender,_:=obj(resultMessage,"sender");recipient,_:=obj(resultMessage,"recipient")
	senderID,_:=str(sender,"peer_id");recipientID,_:=str(recipient,"peer_id")
	if senderID!=remotePeerID||recipientID!=localPeerID{return OperationResultV02{},errors.New("OBIS 0.2 response peer identity mismatch")}
	op,ok:=obj(resultMessage,"operation")
	if !ok||!exactKeys(op,"operation_id","request_hash","state","result","result_ref","failure_code","created_at","updated_at","expires_at"){return OperationResultV02{},errors.New("invalid OBIS 0.2 operation result envelope")}
	gotID,_:=str(op,"operation_id");gotHash,_:=str(op,"request_hash");state,_:=str(op,"state")
	if gotID!=operationID||(expectedHash!=""&&gotHash!=expectedHash){return OperationResultV02{},errors.New("OBIS 0.2 operation identity/hash mismatch")}
	switch state {case "ACCEPTED","RUNNING","SUCCEEDED","FAILED","REJECTED","UNKNOWN","CANCELLED","EXPIRED":default:return OperationResultV02{},errors.New("invalid OBIS 0.2 operation state")}
	created,ok1:=number(op,"created_at");updated,ok2:=number(op,"updated_at");expires,ok3:=number(op,"expires_at")
	if !ok1||!ok2||!ok3||math.IsNaN(created)||math.IsNaN(updated)||math.IsNaN(expires){return OperationResultV02{},errors.New("invalid OBIS 0.2 operation timestamps")}
	var result map[string]any
	if op["result"]!=nil {result,ok=obj(op,"result");if !ok{return OperationResultV02{},errors.New("operation result must be an object or null")}}
	var resultRef,failureCode *string
	if v,ok:=op["result_ref"].(string);ok {resultRef=&v} else if op["result_ref"]!=nil {return OperationResultV02{},errors.New("invalid result_ref")}
	if v,ok:=op["failure_code"].(string);ok {failureCode=&v} else if op["failure_code"]!=nil {return OperationResultV02{},errors.New("invalid failure_code")}
	return OperationResultV02{OperationID:gotID,RequestHash:gotHash,State:state,Result:result,ResultRef:resultRef,FailureCode:failureCode,CreatedAt:created,UpdatedAt:updated,ExpiresAt:expires},nil
}
