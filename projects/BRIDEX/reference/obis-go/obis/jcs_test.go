package obis

import (
	"bytes"
	"testing"
)

func TestCanonicalJCSNumericVector(t *testing.T) {
	input := []byte(`{"numbers":[333333333.33333329,1E30,4.50,2e-3,0.000000000000000000000000001],"literals":[null,true,false]}`)
	want := []byte(`{"literals":[null,true,false],"numbers":[333333333.3333333,1e+30,4.5,0.002,1e-27]}`)
	got, err := CanonicalJCS(input)
	if err != nil { t.Fatalf("CanonicalJCS: %v", err) }
	if !bytes.Equal(got, want) { t.Fatalf("JCS mismatch\n got: %s\nwant: %s", got, want) }
}

func TestCanonicalJCSRejectsDuplicateKeys(t *testing.T) {
	if _, err := CanonicalJCS([]byte(`{"a":1,"a":2}`)); err == nil { t.Fatal("expected duplicate-key rejection") }
}

func TestCanonicalJCSRejectsScalarTopLevel(t *testing.T) {
	if _, err := CanonicalJCS([]byte(`42`)); err == nil { t.Fatal("expected scalar top-level rejection") }
}

func TestCanonicalJCSPropertyOrderingAndUnicode(t *testing.T) {
	input := []byte(`{"z":1,"€":2,"a":3}`)
	want := []byte(`{"a":3,"z":1,"€":2}`)
	got, err := CanonicalJCS(input)
	if err != nil { t.Fatal(err) }
	if !bytes.Equal(got, want) { t.Fatalf("got %s want %s", got, want) }
}
