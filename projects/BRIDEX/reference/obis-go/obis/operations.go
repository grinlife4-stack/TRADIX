package obis

import (
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"math"
	"os"
	"path/filepath"
	"sort"
	"sync"
	"time"
)

var (
	ErrLedgerBusy = errors.New("operation ledger is locked; retry later")
	ErrIdempotencyConflict = errors.New("operation idempotency conflict")
	ErrOperationNotFound = errors.New("operation not found")
	ErrInvalidOperationTransition = errors.New("invalid operation state transition")
)

type OperationRecord struct {
	OperationID string `json:"operation_id"`
	PeerID string `json:"peer_id"`
	PrincipalRef string `json:"principal_ref"`
	CapabilityID string `json:"capability_id"`
	CapabilityVersion string `json:"capability_version"`
	IdempotencyKeyHash string `json:"idempotency_key_hash"`
	RequestHash string `json:"request_hash"`
	State string `json:"state"`
	Result map[string]any `json:"result,omitempty"`
	ResultRef string `json:"result_ref,omitempty"`
	FailureCode string `json:"failure_code,omitempty"`
	CreatedAt float64 `json:"created_at"`
	UpdatedAt float64 `json:"updated_at"`
	ExpiresAt float64 `json:"expires_at"`
}

type operationLedgerFile struct {
	Version int `json:"version"`
	Records map[string]OperationRecord `json:"records"`
}

// FileOperationLedger is a durable owner-local ledger. Atomic directory creation
// serializes writers across processes. A stale .lock directory after a crash is
// intentionally fail-closed and requires operator verification before removal.
type FileOperationLedger struct {
	path string
	lockPath string
	mu sync.Mutex
}

func NewFileOperationLedger(path string) (*FileOperationLedger, error) {
	if path == "" {
		return nil, errors.New("operation ledger path is required")
	}
	absolute, err := filepath.Abs(path)
	if err != nil { return nil, err }
	parent := filepath.Dir(absolute)
	info, err := os.Stat(parent)
	if err != nil { return nil, fmt.Errorf("operation ledger parent: %w", err) }
	if !info.IsDir() { return nil, errors.New("operation ledger parent must be a directory") }
	ledger := &FileOperationLedger{path:absolute, lockPath:absolute+".lock"}
	if _, err := os.Stat(absolute); errors.Is(err, os.ErrNotExist) {
		if err := ledger.withLock(func() error { return ledger.write(operationLedgerFile{Version:1, Records:map[string]OperationRecord{}}) }); err != nil {
			return nil, err
		}
	} else if err != nil { return nil, err }
	return ledger, nil
}

func (l *FileOperationLedger) withLock(fn func() error) error {
	l.mu.Lock()
	defer l.mu.Unlock()
	if err := os.Mkdir(l.lockPath, 0700); err != nil {
		if errors.Is(err, os.ErrExist) { return ErrLedgerBusy }
		return err
	}
	defer os.RemoveAll(l.lockPath)
	owner := []byte(fmt.Sprintf("pid=%d\ncreated=%s\n", os.Getpid(), time.Now().UTC().Format(time.RFC3339Nano)))
	if err := os.WriteFile(filepath.Join(l.lockPath, "owner"), owner, 0600); err != nil { return err }
	return fn()
}

func (l *FileOperationLedger) read() (operationLedgerFile, error) {
	raw, err := os.ReadFile(l.path)
	if err != nil { return operationLedgerFile{}, err }
	var state operationLedgerFile
	if err := json.Unmarshal(raw, &state); err != nil { return operationLedgerFile{}, fmt.Errorf("operation ledger is corrupt: %w", err) }
	if state.Version != 1 || state.Records == nil { return operationLedgerFile{}, errors.New("unsupported or incomplete operation ledger format") }
	return state, nil
}

func (l *FileOperationLedger) write(state operationLedgerFile) error {
	if state.Version != 1 || state.Records == nil { return errors.New("invalid operation ledger state") }
	raw, err := json.Marshal(state)
	if err != nil { return err }
	dir := filepath.Dir(l.path)
	tmp, err := os.CreateTemp(dir, ".obis-operations-*.tmp")
	if err != nil { return err }
	tmpName := tmp.Name()
	defer os.Remove(tmpName)
	if err := tmp.Chmod(0600); err != nil { tmp.Close(); return err }
	if _, err := tmp.Write(raw); err != nil { tmp.Close(); return err }
	if err := tmp.Sync(); err != nil { tmp.Close(); return err }
	if err := tmp.Close(); err != nil { return err }
	if err := os.Rename(tmpName, l.path); err != nil { return err }
	d, err := os.Open(dir)
	if err != nil { return err }
	defer d.Close()
	return d.Sync()
}

func validateOperationText(name, value string) error {
	if value == "" || len(value) > 200 { return fmt.Errorf("%s must be a non-empty string of at most 200 characters", name) }
	return nil
}

func validateRequestHash(value string) error {
	if len(value) != 64 { return errors.New("request_hash must be lowercase SHA-256 hex") }
	decoded, err := hex.DecodeString(value)
	if err != nil || len(decoded) != sha256.Size || hex.EncodeToString(decoded) != value {
		return errors.New("request_hash must be lowercase SHA-256 hex")
	}
	return nil
}

func scopedIdempotencyHash(key string) (string, error) {
	if err := validateOperationText("idempotency_key", key); err != nil { return "", err }
	sum := sha256.Sum256([]byte(key))
	return hex.EncodeToString(sum[:]), nil
}

func (l *FileOperationLedger) Reserve(record OperationRecord, now float64) (OperationRecord, bool, error) {
	for name, value := range map[string]string{
		"operation_id":record.OperationID, "peer_id":record.PeerID,
		"principal_ref":record.PrincipalRef, "capability_id":record.CapabilityID,
		"capability_version":record.CapabilityVersion,
	} { if err := validateOperationText(name, value); err != nil { return OperationRecord{}, false, err } }
	if err := validateRequestHash(record.RequestHash); err != nil { return OperationRecord{}, false, err }
	if err := validateRequestHash(record.IdempotencyKeyHash); err != nil { return OperationRecord{}, false, errors.New("idempotency key hash must be lowercase SHA-256 hex") }
	if !math.IsNaN(now) && !math.IsInf(now, 0) && now >= 0 && !math.IsNaN(record.ExpiresAt) && !math.IsInf(record.ExpiresAt, 0) && record.ExpiresAt > now {
		// valid future expiry
	} else { return OperationRecord{}, false, errors.New("operation expiry must be finite and in the future") }
	var result OperationRecord
	created := false
	err := l.withLock(func() error {
		state, err := l.read(); if err != nil { return err }
		for _, existing := range state.Records {
			sameScope := existing.PeerID == record.PeerID &&
				existing.PrincipalRef == record.PrincipalRef &&
				existing.CapabilityID == record.CapabilityID &&
				existing.CapabilityVersion == record.CapabilityVersion
			if sameScope && existing.IdempotencyKeyHash == record.IdempotencyKeyHash {
				if existing.OperationID != record.OperationID || existing.RequestHash != record.RequestHash {
					return ErrIdempotencyConflict
				}
				result = existing
				return nil
			}
		}
		if existing, ok := state.Records[record.OperationID]; ok {
			if existing.RequestHash != record.RequestHash || existing.IdempotencyKeyHash != record.IdempotencyKeyHash ||
				existing.PeerID != record.PeerID || existing.PrincipalRef != record.PrincipalRef ||
				existing.CapabilityID != record.CapabilityID || existing.CapabilityVersion != record.CapabilityVersion {
				return ErrIdempotencyConflict
			}
			result = existing
			return nil
		}
		record.State = "ACCEPTED"
		record.CreatedAt = now
		record.UpdatedAt = now
		state.Records[record.OperationID] = record
		if err := l.write(state); err != nil { return err }
		result, created = record, true
		return nil
	})
	return result, created, err
}

func (l *FileOperationLedger) Transition(operationID, next string, now float64, result map[string]any, resultRef, failureCode string) (OperationRecord, error) {
	if math.IsNaN(now) || math.IsInf(now, 0) || now < 0 { return OperationRecord{}, errors.New("transition timestamp must be finite and non-negative") }
	var updated OperationRecord
	err := l.withLock(func() error {
		state, err := l.read(); if err != nil { return err }
		record, ok := state.Records[operationID]; if !ok { return ErrOperationNotFound }
		allowed := map[string]map[string]bool{
			"ACCEPTED":{"RUNNING":true,"REJECTED":true,"EXPIRED":true},
			"RUNNING":{"SUCCEEDED":true,"FAILED":true,"UNKNOWN":true,"CANCELLED":true},
		}
		if !allowed[record.State][next] { return fmt.Errorf("%w: %s -> %s", ErrInvalidOperationTransition, record.State, next) }
		if next == "SUCCEEDED" {
			if (result == nil) == (resultRef == "") { return errors.New("SUCCEEDED requires exactly one of result or result_ref") }
		} else if result != nil || resultRef != "" { return errors.New("only SUCCEEDED may contain a result") }
		if (next == "FAILED" || next == "REJECTED") && failureCode == "" { return errors.New("FAILED and REJECTED require failure_code") }
		record.State = next
		record.Result = result
		record.ResultRef = resultRef
		record.FailureCode = failureCode
		record.UpdatedAt = now
		state.Records[operationID] = record
		if err := l.write(state); err != nil { return err }
		updated = record
		return nil
	})
	return updated, err
}

func (l *FileOperationLedger) Get(operationID, peerID, principalRef, capabilityID, capabilityVersion string) (OperationRecord, error) {
	var result OperationRecord
	err := l.withLock(func() error {
		state, err := l.read(); if err != nil { return err }
		record, ok := state.Records[operationID]
		if !ok || record.PeerID != peerID || record.PrincipalRef != principalRef ||
			record.CapabilityID != capabilityID || record.CapabilityVersion != capabilityVersion {
			return ErrOperationNotFound
		}
		result = record
		return nil
	})
	return result, err
}

func (l *FileOperationLedger) RecoverRunningAsUnknown(now float64) (int, error) {
	count := 0
	err := l.withLock(func() error {
		state, err := l.read(); if err != nil { return err }
		keys := make([]string, 0, len(state.Records))
		for key := range state.Records { keys = append(keys, key) }
		sort.Strings(keys)
		for _, key := range keys {
			record := state.Records[key]
			if record.State == "RUNNING" {
				record.State = "UNKNOWN"
				record.FailureCode = "operation.outcome_unknown"
				record.UpdatedAt = now
				state.Records[key] = record
				count++
			}
		}
		if count > 0 { return l.write(state) }
		return nil
	})
	return count, err
}

func (l *FileOperationLedger) IdempotencyKeyHash(key string) (string, error) {
	return scopedIdempotencyHash(key)
}
