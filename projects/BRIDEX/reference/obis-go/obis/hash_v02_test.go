package obis

import (
	"encoding/json"
	"os"
	"path/filepath"
	"testing"
)

func TestOperationRequestHashMatchesPythonProjectionVector(t *testing.T) {
	message := map[string]any{
		"protocol": "obis",
		"version": "0.2",
		"sender": map[string]any{"peer_id": "peer-a"},
		"recipient": map[string]any{"peer_id": "peer-b"},
		"authorization": map[string]any{
			"principal_ref": "principal-a",
			"scopes": []any{"resource.read", "inventory.read"},
		},
		"capability": map[string]any{"id": "ecoscan.inventory.read", "version": "1.0"},
		"payload": map[string]any{"project_id": "project-a", "source_id": "source-1", "limit": 10},
	}
	got, err := OperationRequestHash(message)
	if err != nil { t.Fatal(err) }
	const want = "b065b8b65b60d033cbb8155cfad86eaab5d22a6c63ddbf14eb1243659738c999"
	if got != want { t.Fatalf("hash mismatch: got %s want %s", got, want) }

	reordered := map[string]any{
		"protocol": "obis", "version": "0.2",
		"sender": map[string]any{"peer_id": "peer-a"},
		"recipient": map[string]any{"peer_id": "peer-b"},
		"authorization": map[string]any{
			"principal_ref": "principal-a",
			"scopes": []any{"inventory.read", "resource.read"},
		},
		"capability": map[string]any{"id": "ecoscan.inventory.read", "version": "1.0"},
		"payload": map[string]any{"limit": 10, "source_id": "source-1", "project_id": "project-a"},
	}
	again, err := OperationRequestHash(reordered)
	if err != nil { t.Fatal(err) }
	if again != want { t.Fatalf("scope/object order changed hash: got %s want %s", again, want) }
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


func TestOperationRequestHashUsesSharedContractVectors(t *testing.T) {
	path := filepath.Join("..", "..", "obis-contract", "testdata", "operation-request-hash-vectors.json")
	raw, err := os.ReadFile(path)
	if err != nil { t.Fatal(err) }
	var fixture struct {
		SchemaVersion string `json:"schema_version"`
		Vectors []struct {
			Name string `json:"name"`
			Message map[string]any `json:"message"`
			SHA256 string `json:"sha256"`
		} `json:"vectors"`
	}
	if err := json.Unmarshal(raw, &fixture); err != nil { t.Fatal(err) }
	if fixture.SchemaVersion != "0.2" || len(fixture.Vectors) == 0 {
		t.Fatalf("invalid shared OBIS contract vectors: version=%q count=%d", fixture.SchemaVersion, len(fixture.Vectors))
	}
	for _, vector := range fixture.Vectors {
		t.Run(vector.Name, func(t *testing.T) {
			got, err := OperationRequestHash(vector.Message)
			if err != nil { t.Fatal(err) }
			if got != vector.SHA256 { t.Fatalf("shared vector mismatch: got %s want %s", got, vector.SHA256) }
		})
	}
}
