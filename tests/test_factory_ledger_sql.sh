#!/usr/bin/env bash
set -euo pipefail

container_id="${1:?PostgreSQL service container id is required}"
psql() {
  docker exec -i "$container_id" psql -X -v ON_ERROR_STOP=1 -U postgres -d tradix_test "$@"
}

psql <<'SQL'
INSERT INTO factory.projects (project_id, project_key, display_name, repository_full_name)
VALUES
 ('11111111-1111-4111-8111-111111111111', 'tradix', 'TRADIX', 'grinlife4-stack/TRADIX'),
 ('22222222-2222-4222-8222-222222222222', 'info-engine', 'info_engine', 'grinlife4-stack/info_engine');

INSERT INTO factory.tasks (
  task_id, project_id, task_key, title, request_text, acceptance_criteria,
  risk_class, approval_required
) VALUES
 ('aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',
  '11111111-1111-4111-8111-111111111111', 'ci-task-1',
  'CI ledger test', 'Verify schema constraints.',
  '["tests pass"]'::jsonb, 'low', false),
 ('bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb',
  '22222222-2222-4222-8222-222222222222', 'ci-task-2',
  'Cross-project test', 'Verify task isolation.',
  '["foreign keys hold"]'::jsonb, 'high', true);

INSERT INTO factory.task_attempts (
  attempt_id, task_id, attempt_number, worker_role
) VALUES
 ('cccccccc-cccc-4ccc-8ccc-cccccccccccc',
  'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa', 1, 'implementer'),
 ('dddddddd-dddd-4ddd-8ddd-dddddddddddd',
  'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa', 2, 'implementer'),
 ('eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee',
  'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb', 1, 'implementer');

INSERT INTO factory.task_events (
  event_id, task_id, attempt_id, event_type, to_state, actor_type,
  actor_ref, idempotency_key, payload
) VALUES (
 'ffffffff-ffff-4fff-8fff-ffffffffffff',
 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',
 'cccccccc-cccc-4ccc-8ccc-cccccccccccc',
 'task.created', 'queued', 'system', 'ci-test', 'ci-event-1', '{}'::jsonb
);

INSERT INTO factory.task_approvals (
  approval_id, task_id, approval_round, action, decision, decided_by, rationale
) VALUES (
 '99999999-9999-4999-8999-999999999999',
 'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb',
 1, 'begin_implementation', 'approved', 'ci-test', 'CI fixture'
);

INSERT INTO factory.task_artifacts (
  artifact_id, task_id, attempt_id, artifact_type, object_uri, sha256, byte_size
) VALUES (
 '88888888-8888-4888-8888-888888888888',
 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',
 'cccccccc-cccc-4ccc-8ccc-cccccccccccc',
 'test_report', 'b2://ci-test/test-report.json', repeat('a', 64), 12
);

INSERT INTO factory.task_evidence (
  evidence_id, task_id, attempt_id, artifact_id, evidence_type, recorded_by
) VALUES (
 '77777777-7777-4777-8777-777777777777',
 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',
 'cccccccc-cccc-4ccc-8ccc-cccccccccccc',
 '88888888-8888-4888-8888-888888888888',
 'test_report', 'ci-test'
);
SQL

expect_failure() {
  local label="$1"
  local expected_pattern="$2"
  local statement="$3"
  if psql -c "$statement" >/tmp/tradix-ledger-test.log 2>&1; then
    echo "FAIL: $label unexpectedly succeeded"
    cat /tmp/tradix-ledger-test.log
    exit 1
  fi
  if ! grep -Fq "$expected_pattern" /tmp/tradix-ledger-test.log; then
    echo "FAIL: $label failed for an unexpected reason"
    cat /tmp/tradix-ledger-test.log
    exit 1
  fi
  echo "PASS: $label"
}

expect_failure "high-risk task cannot omit approval requirement" "tasks_check" \
  "INSERT INTO factory.tasks (project_id, task_key, title, request_text, acceptance_criteria, risk_class, approval_required) VALUES ('11111111-1111-4111-8111-111111111111', 'bad-risk', 'bad', 'bad', '[\"x\"]', 'critical', false)"

expect_failure "attempt cannot be attached to another task" "task_events_attempt_id_task_id_fkey" \
  "INSERT INTO factory.task_events (task_id, attempt_id, event_type, actor_type, actor_ref, idempotency_key) VALUES ('aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa', 'eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee', 'bad.cross_task', 'system', 'ci-test', 'bad-cross-task')"

expect_failure "evidence must reference an artifact from the same attempt" "task_evidence_artifact_id_task_id_attempt_id_fkey" \
  "INSERT INTO factory.task_evidence (task_id, attempt_id, artifact_id, evidence_type, recorded_by) VALUES ('aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa', 'dddddddd-dddd-4ddd-8ddd-dddddddddddd', '88888888-8888-4888-8888-888888888888', 'bad_attempt', 'ci-test')"

expect_failure "event idempotency key must be unique" "task_events_idempotency_key_key" \
  "INSERT INTO factory.task_events (task_id, event_type, actor_type, actor_ref, idempotency_key) VALUES ('aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa', 'duplicate', 'system', 'ci-test', 'ci-event-1')"

expect_failure "task events reject UPDATE" "Rows in factory.task_events are append-only" \
  "UPDATE factory.task_events SET event_type = 'tampered' WHERE event_id = 'ffffffff-ffff-4fff-8fff-ffffffffffff'"
expect_failure "task events reject DELETE" "Rows in factory.task_events are append-only" \
  "DELETE FROM factory.task_events WHERE event_id = 'ffffffff-ffff-4fff-8fff-ffffffffffff'"
expect_failure "task events reject TRUNCATE" "Rows in factory.task_events are append-only" \
  "TRUNCATE factory.task_events"

expect_failure "approvals reject UPDATE" "Rows in factory.task_approvals are append-only" \
  "UPDATE factory.task_approvals SET rationale = 'tampered' WHERE approval_id = '99999999-9999-4999-8999-999999999999'"
expect_failure "approvals reject DELETE" "Rows in factory.task_approvals are append-only" \
  "DELETE FROM factory.task_approvals WHERE approval_id = '99999999-9999-4999-8999-999999999999'"
expect_failure "approvals reject TRUNCATE" "Rows in factory.task_approvals are append-only" \
  "TRUNCATE factory.task_approvals"

expect_failure "artifacts reject UPDATE" "Rows in factory.task_artifacts are append-only" \
  "UPDATE factory.task_artifacts SET object_uri = 'b2://tampered' WHERE artifact_id = '88888888-8888-4888-8888-888888888888'"
expect_failure "artifacts reject DELETE" "Rows in factory.task_artifacts are append-only" \
  "DELETE FROM factory.task_artifacts WHERE artifact_id = '88888888-8888-4888-8888-888888888888'"
expect_failure "artifacts reject TRUNCATE" "Rows in factory.task_artifacts are append-only" \
  "TRUNCATE factory.task_artifacts CASCADE"

expect_failure "evidence rejects UPDATE" "Rows in factory.task_evidence are append-only" \
  "UPDATE factory.task_evidence SET description = 'tampered' WHERE evidence_id = '77777777-7777-4777-8777-777777777777'"
expect_failure "evidence rejects DELETE" "Rows in factory.task_evidence are append-only" \
  "DELETE FROM factory.task_evidence WHERE evidence_id = '77777777-7777-4777-8777-777777777777'"
expect_failure "evidence rejects TRUNCATE" "Rows in factory.task_evidence are append-only" \
  "TRUNCATE factory.task_evidence"


-- A third task has no approval record and is used to prove the database gate.
psql <<'SQL'
INSERT INTO factory.tasks (
  task_id, project_id, task_key, title, request_text, acceptance_criteria,
  risk_class, approval_required
) VALUES (
 '33333333-3333-4333-8333-333333333333',
 '22222222-2222-4222-8222-222222222222',
 'ci-task-no-approval', 'Approval gate test', 'Must not start without approval.',
 '["approval required"]'::jsonb, 'high', true
);
SQL

expect_failure "task status cannot be changed directly" "task status must be changed through factory.transition_task" \
  "UPDATE factory.tasks SET status = 'planned' WHERE task_id = 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa'"

psql -v ON_ERROR_STOP=1 -At <<'SQL'
SELECT factory.transition_task(
 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa', 'planned', 'task.planned',
 'system', 'ci-test', 'ci-transition-planned'
);
SQL

# An exact retry returns the original event sequence and does not append twice.
first_seq=$(psql -At -c "SELECT factory.transition_task('aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa','planned','task.planned','system','ci-test','ci-transition-planned')")
retry_seq=$(psql -At -c "SELECT factory.transition_task('aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa','planned','task.planned','system','ci-test','ci-transition-planned')")
if [[ "$first_seq" != "$retry_seq" ]]; then
  echo "FAIL: idempotent retry returned a different event sequence"
  exit 1
fi

expect_failure "idempotency key cannot be reused for different intent" "idempotency key reused with different transition intent" \
  "SELECT factory.transition_task('aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa','blocked','task.blocked','system','ci-test','ci-transition-planned')"

psql -v ON_ERROR_STOP=1 -At <<'SQL'
SELECT factory.transition_task(
 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa', 'implementing', 'task.implementing',
 'system', 'ci-test', 'ci-transition-implementing',
 'cccccccc-cccc-4ccc-8ccc-cccccccccccc'
);
SELECT factory.transition_task(
 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa', 'testing', 'task.testing',
 'system', 'ci-test', 'ci-transition-testing',
 'cccccccc-cccc-4ccc-8ccc-cccccccccccc'
);
SELECT factory.transition_task(
 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa', 'review', 'task.review',
 'system', 'ci-test', 'ci-transition-review',
 'cccccccc-cccc-4ccc-8ccc-cccccccccccc'
);
SQL

expect_failure "candidate requires review evidence" "required evidence missing: review_report" \
  "SELECT factory.transition_task('aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa','candidate','task.candidate','system','ci-test','ci-transition-candidate','cccccccc-cccc-4ccc-8ccc-cccccccccccc')"

psql -v ON_ERROR_STOP=1 -At <<'SQL'
SELECT factory.transition_task(
 '33333333-3333-4333-8333-333333333333', 'planned', 'task.planned',
 'system', 'ci-test', 'ci-noapproval-planned'
);
SQL

expect_failure "high-risk task cannot begin without an approval record" "human approval required before implementation" \
  "SELECT factory.transition_task('33333333-3333-4333-8333-333333333333','implementing','task.implementing','system','ci-test','ci-noapproval-implementing')"

if [[ "$(psql -At -c "SELECT status FROM factory.tasks WHERE task_id='aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa'")" != "review" ]]; then
  echo "FAIL: task projection did not follow the committed event stream"
  exit 1
fi
if [[ "$(psql -At -c "SELECT count(*) FROM factory.task_events WHERE idempotency_key='ci-transition-planned'")" != "1" ]]; then
  echo "FAIL: idempotent retry created duplicate events"
  exit 1
fi

echo "All factory ledger SQL integration checks passed."
