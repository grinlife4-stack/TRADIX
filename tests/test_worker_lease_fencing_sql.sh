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
race_task_id="88888888-8888-4888-8888-888888888888"
race_attempt_id="99999999-9999-4999-8999-999999999999"

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

(runtime_psql "SELECT fencing_token FROM factory.acquire_task_lease('$race_task_id','$race_attempt_id','race-worker-a',30)" > /tmp/tradix-race-a.log 2>&1) &
race_a_pid=$!
(runtime_psql "SELECT fencing_token FROM factory.acquire_task_lease('$race_task_id','$race_attempt_id','race-worker-b',30)" > /tmp/tradix-race-b.log 2>&1) &
race_b_pid=$!
wait "$race_a_pid" || true
wait "$race_b_pid" || true
race_token_a="$(grep -E '^[0-9]+ /tmp/tradix-race-a.log | tail -n 1 || true)"
race_token_b="$(grep -E '^[0-9]+ /tmp/tradix-race-b.log | tail -n 1 || true)"
if [[ -n "$race_token_a" && -z "$race_token_b" ]]; then
  race_worker="race-worker-a"
  race_token="$race_token_a"
elif [[ -n "$race_token_b" && -z "$race_token_a" ]]; then
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
