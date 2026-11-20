package obis

import (
	"bytes"
	"encoding/json"
	"errors"

	jsoncanonicalizer "github.com/cyberphone/json-canonicalization/go/src/webpki.org/jsoncanonicalizer"
)

// CanonicalJCS returns RFC 8785 canonical UTF-8 bytes. The input must be a
// valid I-JSON object or array. Duplicate keys are rejected before canonicalization.
func CanonicalJCS(raw []byte) ([]byte, error) {
	if len(bytes.TrimSpace(raw)) == 0 {
		return nil, errors.New("empty JSON input")
	}
	if _, err := DecodeStrict(raw); err != nil {
		return nil, err
	}
	canonical, err := jsoncanonicalizer.Transform(raw)
	if err != nil {
		return nil, err
	}
	if !json.Valid(canonical) {
		return nil, errors.New("JCS implementation returned invalid JSON")
	}
	return canonical, nil
}

// CanonicalJCSValue serializes a Go value before applying RFC 8785.
// Callers must not use this helper for values whose numeric precision has
// already been lost in a float conversion.
func CanonicalJCSValue(value any) ([]byte, error) {
	raw, err := json.Marshal(value)
	if err != nil {
		return nil, err
	}
	return CanonicalJCS(raw)
}
