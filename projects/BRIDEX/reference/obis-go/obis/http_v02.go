package obis

import (
	"errors"
	"fmt"
	"io"
	"time"
	"net/http"
	"strconv"
)

const MessagePathV02 = "/obis/v0.2/messages"
var errInvalidV02Body = errors.New("invalid OBIS 0.2 request body")

// HandlerV02 exposes the loopback-development OBIS 0.2 endpoint.
// The caller must bind the listener to loopback and configure server timeouts.
func (p *PeerV02) HandlerV02() http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodPost || r.URL.Path != MessagePathV02 {
			http.NotFound(w,r); return
		}
		if r.Header.Get("Content-Type") != "application/obis+json" {
			http.Error(w,"unsupported content type",http.StatusUnsupportedMediaType); return
		}
		if r.Header.Get("Transfer-Encoding") != "" {
			http.Error(w,"transfer encoding unsupported",http.StatusBadRequest); return
		}
		if r.ContentLength <= 0 || r.ContentLength > MaxMessageBytes {
			http.Error(w,"invalid request size",http.StatusRequestEntityTooLarge); return
		}
		r.Body = http.MaxBytesReader(w,r.Body,MaxMessageBytes)
		raw,err := io.ReadAll(r.Body)
		if err != nil || len(raw)==0 || len(raw)>MaxMessageBytes {
			http.Error(w,errInvalidV02Body.Error(),http.StatusBadRequest); return
		}
		message,err := DecodeStrict(raw)
		if err != nil { http.Error(w,"invalid JSON",http.StatusBadRequest); return }
		response,secret,protocolErr := p.Handle(message,r.Header.Get("X-OBIS-Key-Id"),r.Header.Get("X-OBIS-Signature"))
		if protocolErr != nil {
			if len(secret) >= 32 {
				sender,_:=obj(message,"sender")
				senderID,_:=str(sender,"peer_id")
				errorResponse:=map[string]any{
					"protocol":"obis","version":"0.2","message_type":"error_response",
					"message_id":fmt.Sprintf("go-error-%d",time.Now().UnixNano()),
					"correlation_id":message["message_id"],
					"sender":map[string]any{"peer_id":p.Peer.ID},
					"recipient":map[string]any{"peer_id":senderID},
					"issued_at":float64(time.Now().Unix()),
					"error":map[string]any{"code":protocolErr.Code,"message":protocolErr.Message},
				}
				errorBody,encodeErr:=CanonicalJSON(errorResponse)
				if encodeErr==nil {
					responseSignature,signErr:=Sign(errorResponse,secret)
					if signErr==nil {
						w.Header().Set("Content-Type","application/obis+json")
						w.Header().Set("Content-Length",strconv.Itoa(len(errorBody)))
						w.Header().Set("X-OBIS-Signature",responseSignature)
						w.WriteHeader(protocolErr.Status)
						_,_=w.Write(errorBody)
						return
					}
				}
			}
			http.Error(w,protocolErr.Code+": "+protocolErr.Message,protocolErr.Status)
			return
		}
		body,err := CanonicalJSON(response)
		if err != nil { http.Error(w,"response encoding failed",http.StatusInternalServerError); return }
		signature,err := Sign(response,secret)
		if err != nil { http.Error(w,"response signing failed",http.StatusInternalServerError); return }
		w.Header().Set("Content-Type","application/obis+json")
		w.Header().Set("Content-Length",strconv.Itoa(len(body)))
		w.Header().Set("X-OBIS-Signature",signature)
		w.WriteHeader(http.StatusOK)
		_,_ = w.Write(body)
	})
}
