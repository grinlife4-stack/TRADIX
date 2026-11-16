#!/usr/bin/env bash
set -euo pipefail

container_id="${1:?PostgreSQL service container id is required}"
psql() {
  docker exec -i "$container_id" psql -X -v ON_ERROR_STOP=1 -U postgres -d tradix_test "$@"
}

psql <<'SQL'
CREATE ROLE factory_rt_tradix LOGIN INHERIT;
CREATE ROLE factory_rt_info_engine LOGIN INHERIT;
CREATE ROLE factory_approver_tradix LOGIN INHERIT;
CREATE ROLE factory_approver_info_engine LOGIN INHERIT;
CREATE ROLE factory_provisioner LOGIN NOINHERIT;
GRANT factory_runtime TO factory_rt_tradix, factory_rt_info_engine;
GRANT factory_approval_authority TO factory_approver_tradix, factory_approver_info_engine;
GRANT factory_identity_admin TO factory_provisioner WITH SET TRUE, INHERIT FALSE;

INSERT INTO factory.projects (project_id, project_key, display_name, repository_full_name)
VALUES
 ('11111111-1111-4111-8111-111111111111', 'tradix', 'TRADIX', 'grinlife4-stack/TRADIX'),
 ('22222222-2222-4222-8222-222222222222', 'info-engine', 'info_engine', 'grinlife4-stack/info_engine');

SET SESSION AUTHORIZATION factory_provisioner;
SET ROLE factory_identity_admin;
INSERT INTO factory.project_identities (role_name, project_id) VALUES
 ('factory_rt_tradix', '11111111-1111-4111-8111-111111111111'),
 ('factory_rt_info_engine', '22222222-2222-4222-8222-222222222222'),
 ('factory_approver_tradix', '11111111-1111-4111-8111-111111111111'),
 ('factory_approver_info_engine', '22222222-2222-4222-8222-222222222222');
RESET ROLE;
RESET SESSION AUTHORIZATION;

INSERT INTO factory.tasks (
  task_id, project_id, task_key, title, request_text, acceptance_criteria,
  risk_class, approval_required, approval_scope
) VALUES
 ('aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',
  '11111111-1111-4111-8111-111111111111', 'ci-task-1',
  'CI ledger test', 'Verify schema constraints.',
  '["tests pass"]'::jsonb, 'low', false, '{}'::jsonb),
 ('bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb',
  '22222222-2222-4222-8222-222222222222', 'ci-task-2',
  'Cross-project test', 'Verify task isolation.',
  '["foreign keys hold"]'::jsonb, 'high', true, '{"scope":"required"}'::jsonb);

INSERT INTO factory.task_attempts (
  attempt_id, task_id, attempt_number, worker_role
) VALUES
 ('cccccccc-cccc-4ccc-8ccc-cccccccccccc',
  'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa', 1, 'implementer'),
 ('dddddddd-dddd-4ddd-8ddd-dddddddddddd',
  'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa', 2, 'implementer'),
 ('eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee',
  'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb', 1, 'implementer'),
 ('12121212-1212-4212-8212-121212121212',
  'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb', 2, 'implementer'),
 ('13131313-1313-4313-8313-131313131313',
  'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb', 3, 'implementer');

INSERT INTO factory.task_events (
  event_id, task_id, attempt_id, event_type, to_state, actor_type,
  actor_ref, idempotency_key, payload
) VALUES (
 'ffffffff-ffff-4fff-8fff-ffffffffffff',
 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',
 'cccccccc-cccc-4ccc-8ccc-cccccccccccc',
 'task.created', 'queued', 'system', 'ci-test', 'ci-event-1', '{}'::jsonb
);

SET SESSION AUTHORIZATION factory_approver_info_engine;
INSERT INTO factory.task_approvals (
  approval_id, task_id, attempt_id, approval_round, action, decision, decided_by, rationale, decision_scope
) VALUES (
 '99999999-9999-4999-8999-999999999999',
 'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb',
 'eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee',
 1, 'begin_implementation', 'approved', 'ci-test', 'CI fixture', '{"scope":"required"}'::jsonb
);
INSERT INTO factory.task_approvals (
  task_id, attempt_id, approval_round, action, decision, decided_by, rationale, decision_scope
) VALUES (
 'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb',
 '13131313-1313-4313-8313-131313131313',
 1, 'begin_implementation', 'approved', 'ci-test', 'wrong scope fixture', '{"scope":"wrong"}'::jsonb
);
RESET SESSION AUTHORIZATION;

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

psql -c "CREATE ROLE factory_rt_bad LOGIN INHERIT; GRANT factory_runtime, factory_approval_authority TO factory_rt_bad" >/dev/null
expect_failure "a project identity cannot combine runtime and approval authority" "must belong to exactly one of runtime or approval authority" \
  "INSERT INTO factory.project_identities (role_name, project_id) VALUES ('factory_rt_bad', '11111111-1111-4111-8111-111111111111')"

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


# A third task has no approval record and is used to prove the database gate.
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
INSERT INTO factory.task_attempts (attempt_id, task_id, attempt_number, worker_role)
VALUES ('14141414-1414-4414-8414-141414141414', '33333333-3333-4333-8333-333333333333', 1, 'implementer');
SQL

psql -v ON_ERROR_STOP=1 -At <<'SQL'
SET SESSION AUTHORIZATION factory_rt_tradix;
SELECT factory.transition_task(
 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa', 'planned', 'task.planned',
 'system', 'ci-test', 'ci-transition-planned'
);
RESET SESSION AUTHORIZATION;
SQL

# An exact retry returns the original event sequence and does not append twice.
first_seq=$(psql -At -c "SET SESSION AUTHORIZATION factory_rt_tradix; SELECT factory.transition_task('aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa','planned','task.planned','system','ci-test','ci-transition-planned'); RESET SESSION AUTHORIZATION")
retry_seq=$(psql -At -c "SET SESSION AUTHORIZATION factory_rt_tradix; SELECT factory.transition_task('aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa','planned','task.planned','system','ci-test','ci-transition-planned'); RESET SESSION AUTHORIZATION")
if [[ "$first_seq" != "$retry_seq" ]]; then
  echo "FAIL: idempotent retry returned a different event sequence"
  exit 1
fi

expect_failure "idempotency key cannot be reused for different intent" "idempotency key reused with different transition intent" \
  "SET SESSION AUTHORIZATION factory_rt_tradix; SELECT factory.transition_task('aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa','blocked','task.blocked','system','ci-test','ci-transition-planned')"

psql -v ON_ERROR_STOP=1 -At <<'SQL'
SET SESSION AUTHORIZATION factory_rt_tradix;
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
SQL

expect_failure "required evidence cannot be checked without an attempt" "required evidence missing for the specified attempt" \
  "SET SESSION AUTHORIZATION factory_rt_tradix; SELECT factory.transition_task('aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa','review','task.review','system','ci-test','ci-transition-review-null')"
expect_failure "evidence from another attempt cannot satisfy the gate" "required evidence missing for the specified attempt" \
  "SET SESSION AUTHORIZATION factory_rt_tradix; SELECT factory.transition_task('aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa','review','task.review','system','ci-test','ci-transition-review-wrong-attempt','dddddddd-dddd-4ddd-8ddd-dddddddddddd')"

psql -v ON_ERROR_STOP=1 -At <<'SQL'
SET SESSION AUTHORIZATION factory_rt_tradix;
SELECT factory.transition_task(
 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa', 'review', 'task.review',
 'system', 'ci-test', 'ci-transition-review',
 'cccccccc-cccc-4ccc-8ccc-cccccccccccc'
);
RESET SESSION AUTHORIZATION;
SQL

expect_failure "candidate requires review evidence" "required evidence missing for the specified attempt: review_report" \
  "SET SESSION AUTHORIZATION factory_rt_tradix; SELECT factory.transition_task('aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa','candidate','task.candidate','system','ci-test','ci-transition-candidate','cccccccc-cccc-4ccc-8ccc-cccccccccccc')"

psql -v ON_ERROR_STOP=1 -At <<'SQL'
SET SESSION AUTHORIZATION factory_rt_info_engine;
SELECT factory.transition_task(
 '33333333-3333-4333-8333-333333333333', 'planned', 'task.planned',
 'system', 'ci-test', 'ci-noapproval-planned'
);
RESET SESSION AUTHORIZATION;
SQL

expect_failure "high-risk task cannot begin without an approval record" "human approval required for this attempt and decision scope" \
  "SET SESSION AUTHORIZATION factory_rt_info_engine; SELECT factory.transition_task('33333333-3333-4333-8333-333333333333','implementing','task.implementing','system','ci-test','ci-noapproval-implementing','14141414-1414-4414-8414-141414141414')"

psql -v ON_ERROR_STOP=1 -At <<'SQL'
SET SESSION AUTHORIZATION factory_rt_info_engine;
SELECT factory.transition_task(
 'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb', 'planned', 'task.planned',
 'system', 'ci-test', 'ci-approved-planned'
);
RESET SESSION AUTHORIZATION;
SQL
expect_failure "approval from a previous attempt cannot authorize a new attempt" "human approval required for this attempt and decision scope" \
  "SET SESSION AUTHORIZATION factory_rt_info_engine; SELECT factory.transition_task('bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb','implementing','task.implementing','system','ci-test','ci-stale-approval','12121212-1212-4212-8212-121212121212')"
expect_failure "approval with the wrong decision scope cannot authorize implementation" "human approval required for this attempt and decision scope" \
  "SET SESSION AUTHORIZATION factory_rt_info_engine; SELECT factory.transition_task('bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb','implementing','task.implementing','system','ci-test','ci-wrong-scope','13131313-1313-4313-8313-131313131313')"
psql -v ON_ERROR_STOP=1 -At -c "SET SESSION AUTHORIZATION factory_rt_info_engine; SELECT factory.transition_task('bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb','implementing','task.implementing','system','ci-test','ci-approved-implementing','eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee'); RESET SESSION AUTHORIZATION" >/dev/null

if [[ "$(psql -At -c "SELECT status FROM factory.tasks WHERE task_id='aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa'")" != "review" ]]; then
  echo "FAIL: task projection did not follow the committed event stream"
  exit 1
fi
if [[ "$(psql -At -c "SELECT count(*) FROM factory.task_events WHERE idempotency_key='ci-transition-planned'")" != "1" ]]; then
  echo "FAIL: idempotent retry created duplicate events"
  exit 1
fi


# Exercise the application role: it can read and call the transition API,
# but cannot write projections, append events, or mutate immutable records.
runtime_status=$(psql -qAt -c "SET SESSION AUTHORIZATION factory_rt_info_engine; SELECT status FROM factory.tasks WHERE task_id='33333333-3333-4333-8333-333333333333'; RESET SESSION AUTHORIZATION")
if [[ "$runtime_status" != "planned" ]]; then
  echo "FAIL: runtime role cannot read task projection"
  exit 1
fi

psql -v ON_ERROR_STOP=1 -At -c "SET SESSION AUTHORIZATION factory_rt_info_engine; SELECT factory.transition_task('33333333-3333-4333-8333-333333333333','blocked','task.blocked','system','ci-runtime','ci-runtime-transition'); RESET SESSION AUTHORIZATION" >/dev/null
if [[ "$(psql -At -c "SELECT status FROM factory.tasks WHERE task_id='33333333-3333-4333-8333-333333333333'")" != "blocked" ]]; then
  echo "FAIL: runtime role could not transition task through the controlled function"
  exit 1
fi
echo "PASS: runtime role can use the controlled transition function"

expect_failure "runtime cannot claim a human actor identity" "invalid task transition arguments" \
  "SET SESSION AUTHORIZATION factory_rt_info_engine; SELECT factory.transition_task('33333333-3333-4333-8333-333333333333','cancelled','task.cancelled','human','forged-human','ci-forged-human')"

if [[ "$(psql -At -c "SELECT rolsuper::text || ':' || rolcanlogin::text FROM pg_roles WHERE rolname='factory_executor_owner'")" != "false:false" ]]; then
  echo "FAIL: transition function owner must be NOLOGIN and non-superuser"
  exit 1
fi
if [[ "$(psql -At -c "SELECT pg_has_role('tradix_migrator','factory_executor_owner','SET')")" != "t" ]]; then
  echo "FAIL: migration role must be able to SET ROLE to the function owner during ownership transfer"
  exit 1
fi
if [[ "$(psql -At -c "SELECT pg_has_role('tradix_migrator','factory_executor_owner','USAGE')")" != "f" ]]; then
  echo "FAIL: migration role must not inherit function-owner privileges"
  exit 1
fi
if [[ "$(psql -At -c "SELECT rolsuper::text || ':' || rolcreaterole::text FROM pg_roles WHERE rolname='tradix_migrator'")" != "false:false" ]]; then
  echo "FAIL: schema migration actor must be non-superuser without CREATEROLE"
  exit 1
fi
if [[ "$(psql -At -c "SELECT pg_has_role('factory_runtime','factory_executor_owner','MEMBER')")" != "f" ]]; then
  echo "FAIL: runtime role must not be a member of the function-owner role"
  exit 1
fi
if [[ "$(psql -At -c "SELECT pg_has_role('factory_runtime','factory_approval_authority','MEMBER')")" != "f" ]]; then
  echo "FAIL: runtime role must not be a member of human approval authority"
  exit 1
fi
if [[ "$(psql -At -c "SELECT pg_has_role('factory_provisioner','factory_identity_admin','SET') AND NOT pg_has_role('factory_provisioner','factory_identity_admin','USAGE')")" != "t" ]]; then
  echo "FAIL: identity provisioner must have SET-only identity-admin membership"
  exit 1
fi
if [[ "$(psql -At -c "SELECT pg_has_role('factory_rt_tradix','factory_executor_owner','MEMBER') OR pg_has_role('factory_rt_tradix','factory_approval_authority','MEMBER')")" != "f" ]]; then
  echo "FAIL: project runtime identity has privileged role membership"
  exit 1
fi
echo "PASS: function owner, runtime, and approval authority are isolated"


if [[ "$(psql -qAt -c "SET SESSION AUTHORIZATION factory_rt_tradix; SELECT count(*) FROM factory.projects; RESET SESSION AUTHORIZATION")" != "1" ]]; then
  echo "FAIL: TRADIX runtime can see projects outside its identity"
  exit 1
fi
if [[ "$(psql -qAt -c "SET SESSION AUTHORIZATION factory_rt_info_engine; SELECT count(*) FROM factory.projects; RESET SESSION AUTHORIZATION")" != "1" ]]; then
  echo "FAIL: info_engine runtime can see projects outside its identity"
  exit 1
fi
if [[ "$(psql -qAt -c "SET SESSION AUTHORIZATION factory_rt_tradix; SELECT count(*) FROM factory.tasks WHERE task_id='bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb'; RESET SESSION AUTHORIZATION")" != "0" ]]; then
  echo "FAIL: TRADIX runtime can read info_engine tasks"
  exit 1
fi
expect_failure "runtime cannot directly insert an approval" "permission denied" \
  "SET SESSION AUTHORIZATION factory_rt_tradix; INSERT INTO factory.task_approvals (task_id,attempt_id,approval_round,action,decision,decided_by,rationale) VALUES ('aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa','cccccccc-cccc-4ccc-8ccc-cccccccccccc',1,'begin_implementation','approved','forged','forged')"

psql -v ON_ERROR_STOP=1 -c "SET SESSION AUTHORIZATION factory_approver_tradix; INSERT INTO factory.task_approvals (task_id,attempt_id,approval_round,action,decision,decided_by,rationale,decision_scope) VALUES ('aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa','cccccccc-cccc-4ccc-8ccc-cccccccccccc',1,'human_review_test','approved','named-approver','approved by trusted approver','{}'::jsonb); RESET SESSION AUTHORIZATION" >/dev/null
if [[ "$(psql -At -c "SELECT decided_by_login FROM factory.task_approvals WHERE action='human_review_test'")" != "factory_approver_tradix" ]]; then
  echo "FAIL: approval audit did not capture the authentic login identity"
  exit 1
fi

expect_failure "runtime cannot directly update task projection" "permission denied" \
  "SET SESSION AUTHORIZATION factory_rt_info_engine; UPDATE factory.tasks SET status = 'verified' WHERE task_id = '33333333-3333-4333-8333-333333333333'"
expect_failure "runtime cannot directly append task events" "permission denied" \
  "SET SESSION AUTHORIZATION factory_rt_info_engine; INSERT INTO factory.task_events (task_id,event_type,actor_type,actor_ref,idempotency_key) VALUES ('33333333-3333-4333-8333-333333333333','runtime.bypass','system','ci-test','runtime-bypass-event')"
expect_failure "runtime cannot mutate immutable task events" "permission denied" \
  "SET SESSION AUTHORIZATION factory_rt_info_engine; UPDATE factory.task_events SET event_type = 'tampered' WHERE event_id = 'ffffffff-ffff-4fff-8fff-ffffffffffff'"
expect_failure "runtime cannot truncate ledger tables" "permission denied" \
  "SET SESSION AUTHORIZATION factory_rt_info_engine; TRUNCATE factory.tasks"

echo "All factory ledger SQL integration checks passed."
