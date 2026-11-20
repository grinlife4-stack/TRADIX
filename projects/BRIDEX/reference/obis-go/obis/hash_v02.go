package obis

import (
	"crypto/sha256"
	"encoding/hex"
	"errors"
	"sort"
)

func objectField(parent map[string]any, name string) (map[string]any, error) {
	value, ok := parent[name].(map[string]any)
	if !ok {
		return nil, errors.New("OBIS 0.2 hash projection requires object field: " + name)
	}
	return value, nil
}

// OperationRequestHash mirrors Python operation_request_hash exactly.
// It hashes only the normative operation identity/payload projection, not the
// transport envelope, nonce, attempt ID, message timestamps, or operation IDs.
func OperationRequestHash(message map[string]any) (string, error) {
	if message["protocol"] != "obis" || message["version"] != "0.2" {
		return "", errors.New("unsupported OBIS operation hash version")
	}
	sender, err := objectField(message, "sender")
	if err != nil { return "", err }
	recipient, err := objectField(message, "recipient")
	if err != nil { return "", err }
	capability, err := objectField(message, "capability")
	if err != nil { return "", err }
	authorization, err := objectField(message, "authorization")
	if err != nil { return "", err }
	payload, err := objectField(message, "payload")
	if err != nil { return "", err }

	principal, ok := authorization["principal_ref"].(string)
	if !ok || principal == "" { return "", errors.New("invalid principal_ref in operation hash projection") }
	scopesRaw, ok := authorization["scopes"].([]any)
	if !ok || len(scopesRaw) == 0 { return "", errors.New("invalid scopes in operation hash projection") }
	scopes := make([]string, 0, len(scopesRaw))
	for _, raw := range scopesRaw {
		scope, ok := raw.(string)
		if !ok || scope == "" { return "", errors.New("invalid scope in operation hash projection") }
		scopes = append(scopes, scope)
	}
	sort.Strings(scopes)
	for i := 1; i < len(scopes); i++ {
		if scopes[i] == scopes[i-1] { return "", errors.New("duplicate scope in operation hash projection") }
	}

	projection := map[string]any{
		"protocol": "obis",
		"version": "0.2",
		"sender": sender,
		"recipient": recipient,
		"principal_ref": principal,
		"scopes": scopes,
		"capability": capability,
		"payload": payload,
	}
	canonical, err := CanonicalJCSValue(projection)
	if err != nil { return "", err }
	digest := sha256.Sum256(canonical)
	return hex.EncodeToString(digest[:]), nil
}
