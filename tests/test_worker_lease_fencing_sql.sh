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
) VALUES ('$attempt_id', '$task_id', 1, 'implementer');
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

runtime_psql "SELECT factory.transition_task_fenced('$task_id',$token1,'lease-worker-old','planned','task.planned','agent','ci-old-worker','lease-ci-idempotency','$attempt_id','{}'::jsonb)" >/dev/null
echo "PASS: lease owner can perform a fenced transition"

expect_runtime_failure "a second worker cannot acquire a live lease" "task already has a live lease" \
  "SELECT factory.acquire_task_lease('$task_id','$attempt_id','lease-worker-new',5)"

sleep 6
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
