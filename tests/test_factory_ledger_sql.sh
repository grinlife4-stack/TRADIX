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
  local statement="$2"
  if psql -c "$statement" >/tmp/tradix-ledger-test.log 2>&1; then
    echo "FAIL: $label unexpectedly succeeded"
    cat /tmp/tradix-ledger-test.log
    exit 1
  fi
  echo "PASS: $label"
}

expect_failure "high-risk task cannot omit approval requirement"   "INSERT INTO factory.tasks (project_id, task_key, title, request_text, acceptance_criteria, risk_class, approval_required) VALUES ('11111111-1111-4111-8111-111111111111', 'bad-risk', 'bad', 'bad', '[\"x\"]', 'critical', false)"

expect_failure "attempt cannot be attached to another task"   "INSERT INTO factory.task_events (task_id, attempt_id, event_type, actor_type, actor_ref, idempotency_key) VALUES ('aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa', 'eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee', 'bad.cross_task', 'system', 'ci-test', 'bad-cross-task')"

expect_failure "evidence must reference an artifact from the same attempt"   "INSERT INTO factory.task_evidence (task_id, attempt_id, artifact_id, evidence_type, recorded_by) VALUES ('aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa', 'dddddddd-dddd-4ddd-8ddd-dddddddddddd', '88888888-8888-4888-8888-888888888888', 'bad_attempt', 'ci-test')"

expect_failure "event idempotency key must be unique"   "INSERT INTO factory.task_events (task_id, event_type, actor_type, actor_ref, idempotency_key) VALUES ('aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa', 'duplicate', 'system', 'ci-test', 'ci-event-1')"

expect_failure "task events reject UPDATE"   "UPDATE factory.task_events SET event_type = 'tampered' WHERE event_id = 'ffffffff-ffff-4fff-8fff-ffffffffffff'"
expect_failure "task events reject DELETE"   "DELETE FROM factory.task_events WHERE event_id = 'ffffffff-ffff-4fff-8fff-ffffffffffff'"
expect_failure "task events reject TRUNCATE"   "TRUNCATE factory.task_events"

expect_failure "approvals reject UPDATE"   "UPDATE factory.task_approvals SET rationale = 'tampered' WHERE approval_id = '99999999-9999-4999-8999-999999999999'"
expect_failure "approvals reject DELETE"   "DELETE FROM factory.task_approvals WHERE approval_id = '99999999-9999-4999-8999-999999999999'"
expect_failure "approvals reject TRUNCATE"   "TRUNCATE factory.task_approvals"

expect_failure "artifacts reject UPDATE"   "UPDATE factory.task_artifacts SET object_uri = 'b2://tampered' WHERE artifact_id = '88888888-8888-4888-8888-888888888888'"
expect_failure "artifacts reject DELETE"   "DELETE FROM factory.task_artifacts WHERE artifact_id = '88888888-8888-4888-8888-888888888888'"

expect_failure "evidence rejects UPDATE"   "UPDATE factory.task_evidence SET description = 'tampered' WHERE evidence_id = '77777777-7777-4777-8777-777777777777'"
expect_failure "evidence rejects DELETE"   "DELETE FROM factory.task_evidence WHERE evidence_id = '77777777-7777-4777-8777-777777777777'"
expect_failure "evidence rejects TRUNCATE"   "TRUNCATE factory.task_evidence"

echo "All factory ledger SQL integration checks passed."
