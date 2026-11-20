package obis

import "testing"

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
