package obis

import (
	"errors"
	"os"
	"path/filepath"
	"sync"
	"testing"
	"time"
)

func newTestOperationLedger(t *testing.T) *FileOperationLedger {
	t.Helper()
	ledger, err := NewFileOperationLedger(filepath.Join(t.TempDir(), "operations.json"))
	if err != nil { t.Fatal(err) }
	return ledger
}

func reserveTestOperation(t *testing.T, ledger *FileOperationLedger, operationID, key, hash string) (OperationRecord, bool, error) {
	t.Helper()
	keyHash, err := ledger.IdempotencyKeyHash(key)
	if err != nil { t.Fatal(err) }
	return ledger.Reserve(OperationRecord{
		OperationID: operationID, PeerID:"peer:caller", PrincipalRef:"principal:caller",
		CapabilityID:"records.write", CapabilityVersion:"1.0",
		IdempotencyKeyHash:keyHash, RequestHash:hash, ExpiresAt:float64(time.Now().Add(time.Minute).Unix()),
	}, float64(time.Now().Unix()))
}

func TestFileOperationLedgerPersistsReservationAndResultAcrossRestart(t *testing.T) {
	path := filepath.Join(t.TempDir(), "operations.json")
	first, err := NewFileOperationLedger(path); if err != nil { t.Fatal(err) }
	_, created, err := reserveTestOperation(t, first, "op-1", "key-1", "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa")
	if err != nil || !created { t.Fatalf("reserve: created=%v err=%v", created, err) }
	if _, err := first.Transition("op-1", "RUNNING", float64(time.Now().Unix()), nil, "", ""); err != nil { t.Fatal(err) }
	if _, err := first.Transition("op-1", "SUCCEEDED", float64(time.Now().Unix()), map[string]any{"written":true}, "", ""); err != nil { t.Fatal(err) }
	restarted, err := NewFileOperationLedger(path); if err != nil { t.Fatal(err) }
	record, err := restarted.Get("op-1","peer:caller","principal:caller","records.write","1.0")
	if err != nil || record.State != "SUCCEEDED" || record.Result["written"] != true { t.Fatalf("recovered record: %#v err=%v", record, err) }
}

func TestFileOperationLedgerIdempotencyConflicts(t *testing.T) {
	ledger := newTestOperationLedger(t)
	_, created, err := reserveTestOperation(t, ledger, "op-1", "key-1", "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa")
	if err != nil || !created { t.Fatalf("first reserve: %v", err) }
	_, _, err = reserveTestOperation(t, ledger, "op-2", "key-1", "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa")
	if !errors.Is(err, ErrIdempotencyConflict) { t.Fatalf("expected key conflict, got %v", err) }
	_, _, err = reserveTestOperation(t, ledger, "op-1", "key-2", "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb")
	if !errors.Is(err, ErrIdempotencyConflict) { t.Fatalf("expected operation conflict, got %v", err) }
}

func TestFileOperationLedgerConcurrentReservationIsFailClosed(t *testing.T) {
	path := filepath.Join(t.TempDir(), "operations.json")
	first, err := NewFileOperationLedger(path); if err != nil { t.Fatal(err) }
	second, err := NewFileOperationLedger(path); if err != nil { t.Fatal(err) }
	var wg sync.WaitGroup
	var mu sync.Mutex
	created := 0
	busy := 0
	for _, ledger := range []*FileOperationLedger{first,second} {
		wg.Add(1)
		go func(l *FileOperationLedger) {
			defer wg.Done()
			_, wasCreated, err := reserveTestOperation(t, l, "op-1", "key-1", "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa")
			mu.Lock(); defer mu.Unlock()
			if err == nil && wasCreated { created++ } else if errors.Is(err, ErrLedgerBusy) { busy++ } else if err != nil { t.Errorf("unexpected reservation error: %v", err) }
		}(ledger)
	}
	wg.Wait()
	if created != 1 || busy > 1 { t.Fatalf("expected one durable claim; created=%d busy=%d", created,busy) }
}

func TestFileOperationLedgerCrashRecoveryMarksRunningUnknown(t *testing.T) {
	ledger := newTestOperationLedger(t)
	reserveTestOperation(t, ledger, "op-1", "key-1", "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa")
	if _, err := ledger.Transition("op-1","RUNNING",float64(time.Now().Unix()),nil,"",""); err != nil { t.Fatal(err) }
	count, err := ledger.RecoverRunningAsUnknown(float64(time.Now().Unix()))
	if err != nil || count != 1 { t.Fatalf("recovery count=%d err=%v",count,err) }
	record, err := ledger.Get("op-1","peer:caller","principal:caller","records.write","1.0")
	if err != nil || record.State != "UNKNOWN" { t.Fatalf("record=%#v err=%v",record,err) }
}

func TestFileOperationLedgerStaleLockFailsClosed(t *testing.T) {
	ledger := newTestOperationLedger(t)
	if err := os.Mkdir(ledger.lockPath,0700); err != nil { t.Fatal(err) }
	_, _, err := reserveTestOperation(t, ledger, "op-1", "key-1", "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa")
	if !errors.Is(err,ErrLedgerBusy) { t.Fatalf("expected fail-closed lock error, got %v",err) }
}

func TestFileOperationLedgerStatusIsIdentityScoped(t *testing.T) {
	ledger := newTestOperationLedger(t)
	reserveTestOperation(t, ledger, "op-1", "key-1", "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa")
	if _, err := ledger.Get("op-1","peer:attacker","principal:caller","records.write","1.0"); !errors.Is(err,ErrOperationNotFound) {
		t.Fatalf("expected scoped not-found, got %v",err)
	}
}


func TestFileOperationLedgerRejectsInvalidIdempotencyHash(t *testing.T) {
	ledger := newTestOperationLedger(t)
	_, _, err := ledger.Reserve(OperationRecord{
		OperationID:"op-bad", PeerID:"peer:caller", PrincipalRef:"principal:caller",
		CapabilityID:"records.write", CapabilityVersion:"1.0",
		IdempotencyKeyHash:"not-a-hash",
		RequestHash:"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
		ExpiresAt:float64(time.Now().Add(time.Minute).Unix()),
	}, float64(time.Now().Unix()))
	if err == nil { t.Fatal("expected invalid idempotency hash to be rejected") }
}
