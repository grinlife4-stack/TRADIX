#!/usr/bin/env bash
set -euo pipefail

container_id="${1:?PostgreSQL service container id is required}"
psql() {
  docker exec -i "$container_id" psql -X -qAt -v ON_ERROR_STOP=1 -U postgres -d tradix_test "$@"
}
runtime_psql() {
  local sql="$1"
  docker exec -i "$container_id" psql -X -qAt -v ON_ERROR_STOP=1 -U postgres -d tradix_test -c "SET SESSION AUTHORIZATION factory_rt_tradix; $sql"
}
identity_psql() {
  local identity="$1"
  local sql="$2"
  docker exec -i "$container_id" psql -X -qAt -v ON_ERROR_STOP=1 -U postgres -d tradix_test -c "SET SESSION AUTHORIZATION $identity; $sql"
}
expect_identity_failure() {
  local identity="$1"
  local label="$2"
  local expected="$3"
  local sql="$4"
  if identity_psql "$identity" "$sql" >/tmp/tradix-lease-identity-test.log 2>&1; then
    echo "FAIL: $label unexpectedly succeeded"
    cat /tmp/tradix-lease-identity-test.log
    exit 1
  fi
  if ! grep -Fq "$expected" /tmp/tradix-lease-identity-test.log; then
    echo "FAIL: $label failed for an unexpected reason"
    cat /tmp/tradix-lease-identity-test.log
    exit 1
  fi
  echo "PASS: $label"
}
expect_runtime_failure() {
  local label="$1"
  local expected="$2"
  local sql="$3"
  if runtime_psql "$sql" >/tmp/tradix-lease-test.log 2>&1; then
    echo "FAIL: $label unexpectedly succeeded"
    cat /tmp/tradix-lease-test.log
    exit 1
  fi
  if ! grep -Fq "$expected" /tmp/tradix-lease-test.log; then
    echo "FAIL: $label failed for an unexpected reason"
    cat /tmp/tradix-lease-test.log
    exit 1
  fi
  echo "PASS: $label"
}

task_id="55555555-5555-4555-8555-555555555555"
attempt_id="66666666-6666-4666-8666-666666666666"
next_attempt_id="77777777-7777-4777-8777-777777777777"
race_task_id="f1f1f1f1-f1f1-41f1-81f1-f1f1f1f1f1f1"
race_attempt_id="e1e1e1e1-e1e1-41e1-81e1-e1e1e1e1e1e1"
lock_task_id="f2f2f2f2-f2f2-42f2-82f2-f2f2f2f2f2f2"
lock_attempt_id="e2e2e2e2-e2e2-42e2-82e2-e2e2e2e2e2e2"
rollback_task_id="f3f3f3f3-f3f3-43f3-83f3-f3f3f3f3f3f3"
rollback_attempt_id="e3e3e3e3-e3e3-43e3-83e3-e3e3e3e3e3e3"

psql <<SQL
INSERT INTO factory.tasks (
  task_id, project_id, task_key, title, request_text, acceptance_criteria,
  risk_class, approval_required
) VALUES (
  '$task_id', '11111111-1111-4111-8111-111111111111',
  'lease-fencing-ci', 'Lease fencing CI', 'Prove stale workers cannot write.',
  '["fencing enforced"]'::jsonb, 'low', false
);
INSERT INTO factory.task_attempts (
  attempt_id, task_id, attempt_number, worker_role
 ) VALUES
 ('$attempt_id', '$task_id', 1, 'implementer'),
 ('$next_attempt_id', '$task_id', 2, 'implementer');
INSERT INTO factory.tasks (
  task_id, project_id, task_key, title, request_text, acceptance_criteria,
  risk_class, approval_required
) VALUES (
  '$race_task_id', '11111111-1111-4111-8111-111111111111',
  'lease-race-ci', 'Lease race CI', 'Only one simultaneous acquirer may win.',
  '["one lease owner"]'::jsonb, 'low', false
);
INSERT INTO factory.task_attempts (attempt_id, task_id, attempt_number, worker_role)
VALUES ('$race_attempt_id', '$race_task_id', 1, 'implementer');
INSERT INTO factory.tasks (
  task_id, project_id, task_key, title, request_text, acceptance_criteria,
  risk_class, approval_required
) VALUES (
  '$lock_task_id', '11111111-1111-4111-8111-111111111111',
  'lease-write-lock-ci', 'Lease write lock CI', 'Serialize stale writes against takeover.',
  '["write lock serialization"]'::jsonb, 'low', false
);
INSERT INTO factory.task_attempts (attempt_id, task_id, attempt_number, worker_role)
VALUES ('$lock_attempt_id', '$lock_task_id', 1, 'implementer');
INSERT INTO factory.tasks (
  task_id, project_id, task_key, title, request_text, acceptance_criteria,
  risk_class, approval_required
) VALUES (
  '$rollback_task_id', '11111111-1111-4111-8111-111111111111',
  'lease-atomic-rollback-ci', 'Lease atomic rollback CI', 'Prove terminal writes roll back together.',
  '["atomic completion"]'::jsonb, 'low', false
);
INSERT INTO factory.task_attempts (attempt_id, task_id, attempt_number, worker_role)
VALUES ('$rollback_attempt_id', '$rollback_task_id', 1, 'implementer');
SQL

if [[ "$(psql -c "SELECT status FROM factory.task_attempts WHERE attempt_id='$attempt_id'")" != "queued" ]]; then
  echo "FAIL: new attempts must remain queued until lease acquisition"
  exit 1
fi
echo "PASS: attempt creation remains queued until lease acquisition"

token1="$(runtime_psql "SELECT fencing_token FROM factory.acquire_task_lease('$task_id','$attempt_id','lease-worker-old',5)")"
if [[ -z "$token1" ]]; then
  echo "FAIL: first worker did not receive a fencing token"
  exit 1
fi

expect_identity_failure "factory_rt_info_engine" "another product cannot renew TRADIX lease" "lease is missing, expired, or owned by another worker" \
  "SELECT factory.renew_task_lease('$task_id','$attempt_id','lease-worker-old',$token1,30)"
expect_identity_failure "factory_rt_info_engine" "another product cannot acquire TRADIX lease" "task not found for this product runtime" \
  "SELECT factory.acquire_task_lease('$task_id','$attempt_id','foreign-worker',30)"
expect_runtime_failure "wrong worker cannot renew a lease" "lease is missing, expired, or owned by another worker" \
  "SELECT factory.renew_task_lease('$task_id','$attempt_id','different-worker',$token1,5)"
expect_runtime_failure "wrong attempt cannot renew a lease" "lease is missing, expired, or owned by another worker" \
  "SELECT factory.renew_task_lease('$task_id','$next_attempt_id','lease-worker-old',$token1,5)"
wrong_token=$((token1 + 1))
expect_runtime_failure "wrong fencing token cannot renew a lease" "lease is missing, expired, or owned by another worker" \
  "SELECT factory.renew_task_lease('$task_id','$attempt_id','lease-worker-old',$wrong_token,5)"
renewed_until="$(runtime_psql "SELECT factory.renew_task_lease('$task_id','$attempt_id','lease-worker-old',$token1,5)")"
if [[ -z "$renewed_until" ]]; then
  echo "FAIL: current owner could not renew its lease"
  exit 1
fi
echo "PASS: current owner can renew the exact live lease"

runtime_psql "SELECT factory.transition_task_fenced('$task_id',$token1,'lease-worker-old','planned','task.planned','agent','ci-old-worker','lease-ci-idempotency','$attempt_id','{}'::jsonb)" >/dev/null
echo "PASS: lease owner can perform a fenced transition"

expect_runtime_failure "a second worker cannot acquire a live lease" "task already has a live lease" \
  "SELECT factory.acquire_task_lease('$task_id','$attempt_id','lease-worker-new',5)"

sleep 6
expect_runtime_failure "expired lease cannot silently switch to a different attempt" "expired lease belongs to another attempt" \
  "SELECT factory.acquire_task_lease('$task_id','$next_attempt_id','lease-worker-new',30)"
token2="$(runtime_psql "SELECT fencing_token FROM factory.acquire_task_lease('$task_id','$attempt_id','lease-worker-new',30)")"
if [[ -z "$token2" || "$token2" -le "$token1" ]]; then
  echo "FAIL: takeover did not issue a strictly increasing fencing token"
  exit 1
fi
echo "PASS: expired lease takeover issues a larger fencing token"

expect_runtime_failure "stale worker cannot replay an idempotent transition" "valid task lease and fencing token required" \
  "SELECT factory.transition_task_fenced('$task_id',$token1,'lease-worker-old','planned','task.planned','agent','ci-old-worker','lease-ci-idempotency','$attempt_id','{}'::jsonb)"
expect_runtime_failure "stale worker cannot append evidence" "valid task lease and fencing token required" \
  "SELECT factory.record_task_evidence_fenced('$task_id','$attempt_id','lease-worker-old',$token1,'test_report','ci://stale/evidence','aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',1,'text/plain','test_report','stale worker evidence','{}'::jsonb)"
expect_runtime_failure "stale worker cannot finish an attempt" "valid task lease and fencing token required" \
  "SELECT factory.finish_task_attempt_fenced('$task_id','$attempt_id','lease-worker-old',$token1,'failed')"
expect_runtime_failure "stale worker cannot renew its expired lease" "lease is missing, expired, or owned by another worker" \
  "SELECT factory.renew_task_lease('$task_id','$attempt_id','lease-worker-old',$token1,30)"
echo "PASS: every stale-worker write path is fenced"

runtime_psql "SELECT factory.transition_task_fenced('$task_id',$token2,'lease-worker-new','implementing','task.implementing','agent','ci-new-worker','lease-ci-new-transition','$attempt_id','{}'::jsonb)" >/dev/null
runtime_psql "SELECT factory.finish_task_attempt_fenced('$task_id','$attempt_id','lease-worker-new',$token2,'failed')" >/dev/null
runtime_psql "SELECT factory.release_task_lease('$task_id','$attempt_id','lease-worker-new',$token2)" >/dev/null

if [[ "$(psql -c "SELECT count(*) FROM factory.task_leases WHERE task_id='$task_id'")" != "0" ]]; then
  echo "FAIL: terminal attempt retained its lease"
  exit 1
fi
if [[ "$(psql -c "SELECT status FROM factory.task_attempts WHERE attempt_id='$attempt_id'")" != "failed" ]]; then
  echo "FAIL: current lease owner could not finish the attempt"
  exit 1
fi
echo "PASS: current lease owner can finish and release atomically controlled ownership"

expect_runtime_failure "runtime cannot bypass fencing through legacy transition" "permission denied for function transition_task" \
  "SELECT factory.transition_task('$task_id','blocked','task.blocked','agent','legacy-bypass','legacy-transition','$attempt_id')"
expect_runtime_failure "runtime cannot bypass fencing through legacy evidence API" "permission denied for function record_task_evidence" \
  "SELECT factory.record_task_evidence('$task_id','$attempt_id','test_report','ci://legacy/evidence','aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',1,'text/plain','test_report')"
expect_runtime_failure "runtime cannot bypass fencing through legacy finish API" "permission denied for function finish_task_attempt" \
  "SELECT factory.finish_task_attempt('$task_id','$attempt_id','failed')"
expect_runtime_failure "runtime cannot inspect or mutate lease tables directly" "permission denied for table task_leases" \
  "SELECT * FROM factory.task_leases"

lock_token_old="$(runtime_psql "SELECT fencing_token FROM factory.acquire_task_lease('$lock_task_id','$lock_attempt_id','lock-worker-old',5)")"
(
  docker exec -i "$container_id" psql -X -qAt -v ON_ERROR_STOP=1 -U postgres -d tradix_test <<SQL
SET SESSION AUTHORIZATION factory_rt_tradix;
BEGIN;
SELECT factory.record_task_evidence_fenced(
  '$lock_task_id', '$lock_attempt_id', 'lock-worker-old', $lock_token_old,
  'test_report', 'ci://lease-lock/old-worker',
  'cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc',
  1, 'text/plain', 'test_report', 'write held open across expiry', '{}'::jsonb
);
SELECT pg_sleep(10);
COMMIT;
SQL
) >/tmp/tradix-lease-write-lock.log 2>&1 &
lock_writer_pid=$!
sleep 6
lock_started_ms="$(date +%s%3N)"
lock_token_new="$(runtime_psql "SELECT fencing_token FROM factory.acquire_task_lease('$lock_task_id','$lock_attempt_id','lock-worker-new',30)")"
lock_elapsed_ms=$(( $(date +%s%3N) - lock_started_ms ))
wait "$lock_writer_pid"
if [[ -z "$lock_token_new" || "$lock_token_new" -le "$lock_token_old" ]]; then
  echo "FAIL: takeover did not fence the long-running write transaction"
  cat /tmp/tradix-lease-write-lock.log
  exit 1
fi
if [[ "$lock_elapsed_ms" -lt 2500 ]]; then
  echo "FAIL: takeover was not serialized behind the in-flight fenced write"
  echo "elapsed_ms=$lock_elapsed_ms"
  cat /tmp/tradix-lease-write-lock.log
  exit 1
fi
expect_runtime_failure "old worker cannot write after serialized takeover" "valid task lease and fencing token required" \
  "SELECT factory.record_task_evidence_fenced('$lock_task_id','$lock_attempt_id','lock-worker-old',$lock_token_old,'test_report','ci://lease-lock/stale-after','dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd',1,'text/plain','test_report')"
echo "PASS: lease takeover serializes against in-flight evidence writes"

runtime_psql "SELECT factory.finish_task_attempt_fenced('$lock_task_id','$lock_attempt_id','lock-worker-new',$lock_token_new,'failed')" >/dev/null
expect_runtime_failure "completed attempt cannot record new evidence" "evidence can only be recorded for a running attempt" \
  "SELECT factory.record_task_evidence_fenced('$lock_task_id','$lock_attempt_id','lock-worker-new',$lock_token_new,'test_report','ci://lease-lock/after-finish','eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee',1,'text/plain','test_report')"
runtime_psql "BEGIN; SELECT factory.transition_task_fenced('$lock_task_id',$lock_token_new,'lock-worker-new','failed','task.failed','agent','lock-worker-new','lock-worker-final','$lock_attempt_id','{}'::jsonb); SELECT factory.release_task_lease('$lock_task_id','$lock_attempt_id','lock-worker-new',$lock_token_new); COMMIT" >/dev/null
expect_runtime_failure "released lease cannot be renewed" "lease is missing, expired, or owned by another worker" \
  "SELECT factory.renew_task_lease('$lock_task_id','$lock_attempt_id','lock-worker-new',$lock_token_new,30)"
echo "PASS: current lease owner can finish, transition, and release after takeover"

(runtime_psql "SELECT fencing_token FROM factory.acquire_task_lease('$race_task_id','$race_attempt_id','race-worker-a',30)" > /tmp/tradix-race-a.log 2>&1) &
race_a_pid=$!
(runtime_psql "SELECT fencing_token FROM factory.acquire_task_lease('$race_task_id','$race_attempt_id','race-worker-b',30)" > /tmp/tradix-race-b.log 2>&1) &
race_b_pid=$!
wait "$race_a_pid" || true
wait "$race_b_pid" || true
race_token_a="$(tail -n 1 /tmp/tradix-race-a.log)"
race_token_b="$(tail -n 1 /tmp/tradix-race-b.log)"
if [[ "$race_token_a" =~ ^[0-9]+$ && ! "$race_token_b" =~ ^[0-9]+$ ]]; then
  race_worker="race-worker-a"
  race_token="$race_token_a"
elif [[ "$race_token_b" =~ ^[0-9]+$ && ! "$race_token_a" =~ ^[0-9]+$ ]]; then
  race_worker="race-worker-b"
  race_token="$race_token_b"
else
  echo "FAIL: simultaneous acquisition did not produce exactly one winner"
  cat /tmp/tradix-race-a.log /tmp/tradix-race-b.log
  exit 1
fi
runtime_psql "SELECT factory.finish_task_attempt_fenced('$race_task_id','$race_attempt_id','$race_worker',$race_token,'failed')" >/dev/null
runtime_psql "SELECT factory.release_task_lease('$race_task_id','$race_attempt_id','$race_worker',$race_token)" >/dev/null
echo "PASS: concurrent lease acquisition produces exactly one owner"

rollback_token="$(runtime_psql "SELECT fencing_token FROM factory.acquire_task_lease('$rollback_task_id','$rollback_attempt_id','rollback-worker',30)")"
if runtime_psql "BEGIN; SELECT factory.finish_task_attempt_fenced('$rollback_task_id','$rollback_attempt_id','rollback-worker',$rollback_token,'failed'); SELECT factory.transition_task_fenced('$rollback_task_id',$rollback_token,'rollback-worker','failed','task.failed','agent','rollback-worker','rollback-failpoint','$rollback_attempt_id','{}'::jsonb); SELECT factory.release_task_lease('$rollback_task_id','$rollback_attempt_id','rollback-worker',$rollback_token); SELECT 1/0; COMMIT" >/tmp/tradix-lease-rollback.log 2>&1; then
  echo "FAIL: injected finalization error unexpectedly committed"
  exit 1
fi
rollback_state="$(psql -c "SELECT t.status || '/' || a.status || '/' || (SELECT count(*) FROM factory.task_leases l WHERE l.task_id=t.task_id)::text FROM factory.tasks t JOIN factory.task_attempts a ON a.task_id=t.task_id WHERE t.task_id='$rollback_task_id'")"
if [[ "$rollback_state" != "queued/running/1" ]]; then
  echo "FAIL: terminal finalization was not rolled back atomically: $rollback_state"
  cat /tmp/tradix-lease-rollback.log
  exit 1
fi
runtime_psql "BEGIN; SELECT factory.finish_task_attempt_fenced('$rollback_task_id','$rollback_attempt_id','rollback-worker',$rollback_token,'failed'); SELECT factory.transition_task_fenced('$rollback_task_id',$rollback_token,'rollback-worker','failed','task.failed','agent','rollback-worker','rollback-final','$rollback_attempt_id','{}'::jsonb); SELECT factory.release_task_lease('$rollback_task_id','$rollback_attempt_id','rollback-worker',$rollback_token); COMMIT" >/dev/null
rollback_final_state="$(psql -c "SELECT t.status || '/' || a.status || '/' || (SELECT count(*) FROM factory.task_leases l WHERE l.task_id=t.task_id)::text FROM factory.tasks t JOIN factory.task_attempts a ON a.task_id=t.task_id WHERE t.task_id='$rollback_task_id'")"
if [[ "$rollback_final_state" != "failed/failed/0" ]]; then
  echo "FAIL: atomic terminal completion did not produce the expected state: $rollback_final_state"
  exit 1
fi
echo "PASS: terminal attempt, task transition, and lease release roll back or commit together"
