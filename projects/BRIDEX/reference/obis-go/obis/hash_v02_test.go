package obis

import (
	"encoding/json"
	"os"
	"path/filepath"
	"testing"
)

func TestOperationRequestHashMatchesSharedVector(t *testing.T) {
	raw,err:=os.ReadFile(filepath.Join("..","..","obis-contract","testdata","operation-request-hash-vectors.json"))
	if err!=nil{t.Fatal(err)}
	var fixture struct {
		SchemaVersion string `json:"schema_version"`
		Vectors []struct {
			Name string `json:"name"`
			Message map[string]any `json:"message"`
			SHA256 string `json:"sha256"`
		} `json:"vectors"`
	}
	decoder:=json.NewDecoder(bytes.NewReader(raw))
	decoder.UseNumber()
	if err=decoder.Decode(&fixture);err!=nil{t.Fatal(err)}
	if fixture.SchemaVersion!="0.2"||len(fixture.Vectors)==0{t.Fatal("shared OBIS 0.2 hash vectors are missing or unsupported")}
	for _,vector:=range fixture.Vectors{
		t.Run(vector.Name,func(t *testing.T){
			got,err:=OperationRequestHash(vector.Message)
			if err!=nil{t.Fatal(err)}
			if got!=vector.SHA256{t.Fatalf("hash mismatch: got %s want %s",got,vector.SHA256)}
		})
	}
}

func TestOperationRequestHashRejectsDuplicateScopes(t *testing.T) {
	message := map[string]any{
		"protocol": "obis", "version": "0.2",
		"sender": map[string]any{"peer_id": "peer-a"},
		"recipient": map[string]any{"peer_id": "peer-b"},
		"authorization": map[string]any{"principal_ref": "principal-a", "scopes": []any{"read", "read"}},
		"capability": map[string]any{"id": "cap", "version": "1"},
		"payload": map[string]any{},
	}
	if _, err := OperationRequestHash(message); err == nil { t.Fatal("expected duplicate scope rejection") }
}

