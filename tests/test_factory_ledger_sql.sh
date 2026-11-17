#!/usr/bin/env bash
set -euo pipefail

container_id="${1:?PostgreSQL service container id is required}"
psql() {
  docker exec -i "$container_id" psql -X -v ON_ERROR_STOP=1 -U postgres -d tradix_test "$@"
}

provision_logins() {
  docker exec -i "$container_id" psql -X -v ON_ERROR_STOP=1 -U postgres -d tradix_test -v runtime_login="$1" -v approval_login="$2" -v provisioner_login=factory_provisioner < migrations/operations/create_product_logins.sql
}

provision_logins factory_rt_tradix factory_approver_tradix
provision_logins factory_rt_info_engine factory_approver_info_engine
provision_logins factory_rt_physical_goods factory_approver_physical_goods
provision_logins factory_rt_onboarding factory_approver_onboarding
provision_logins factory_rt_onboarding_extra factory_approver_onboarding_extra
provision_logins factory_rt_wrong_kind factory_approver_wrong_kind
psql -c "ALTER ROLE factory_rt_tradix PASSWORD 'ci-only-factory-dossier-password'" >/dev/null

psql <<'SQL'
INSERT INTO factory.projects (
  project_id, project_key, display_name, product_type, repository_full_name
) VALUES
 ('11111111-1111-4111-8111-111111111111', 'tradix', 'TRADIX', 'software', 'grinlife4-stack/TRADIX'),
 ('22222222-2222-4222-8222-222222222222', 'info-engine', 'info_engine', 'software', 'grinlife4-stack/info_engine'),
 ('44444444-4444-4444-8444-444444444444', 'physical-goods', 'Physical Goods Product', 'physical', NULL);

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM factory.projects
    WHERE project_key = 'physical-goods'
      AND product_type = 'physical'
      AND repository_full_name IS NULL
  ) THEN
    RAISE EXCEPTION 'non-software product without a Git repository was not registered';
  END IF;
END;
$$;

SET SESSION AUTHORIZATION factory_provisioner;
SET ROLE factory_identity_admin;
INSERT INTO factory.project_identities (role_name, project_id, identity_kind) VALUES
 ('factory_rt_tradix', '11111111-1111-4111-8111-111111111111', 'runtime'),
 ('factory_rt_info_engine', '22222222-2222-4222-8222-222222222222', 'runtime'),
 ('factory_rt_physical_goods', '44444444-4444-4444-8444-444444444444', 'runtime'),
 ('factory_approver_tradix', '11111111-1111-4111-8111-111111111111', 'approval'),
 ('factory_approver_info_engine', '22222222-2222-4222-8222-222222222222', 'approval');
RESET ROLE;
RESET SESSION AUTHORIZATION;
SQL

onboarding_output=$(docker exec -i "$container_id" psql -X -qAt -v ON_ERROR_STOP=1 -U factory_provisioner -d tradix_test \
  -v project_key=onboarding-smoke \
  -v display_name="Onboarding Smoke Product" \
  -v product_type=service \
  -v repository_full_name= \
  -v runtime_login=factory_rt_onboarding \
  -v approval_login=factory_approver_onboarding \
  < migrations/operations/register_product.sql)
onboarding_project_id=$(printf '%s\n' "$onboarding_output" | sed -n 's/^Product registered with project_id=//p')
if [[ -z "$onboarding_project_id" ]]; then
  echo "FAIL: product registration script did not return a project id"
  printf '%s\n' "$onboarding_output"
  exit 1
fi
if [[ "$(psql -At -c "SELECT count(*) FROM factory.project_identities WHERE project_id='$onboarding_project_id'")" != "2" ]]; then
  echo "FAIL: product registration did not create exactly two identity mappings"
  exit 1
fi

# The restricted product runtime is exercised by the manifest-driven executor step in CI.
psql -c "ALTER ROLE factory_rt_onboarding PASSWORD 'ci-only-onboarding-password'" >/dev/null

psql <<'SQL'
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
  "INSERT INTO factory.project_identities (role_name, project_id, identity_kind) VALUES ('factory_rt_bad', '11111111-1111-4111-8111-111111111111', 'runtime')"

expect_failure "identity kind must match the granted authority" "identity kind does not match its authority role" \
  "INSERT INTO factory.project_identities (role_name, project_id, identity_kind) VALUES ('factory_rt_wrong_kind', '11111111-1111-4111-8111-111111111111', 'approval')"

expect_failure "a product cannot have two runtime LOGIN identities" "project_identities_project_id_identity_kind_key" \
  "INSERT INTO factory.project_identities (role_name, project_id, identity_kind) VALUES ('factory_rt_onboarding_extra', '$onboarding_project_id', 'runtime')"

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

expect_failure "runtime cannot directly create a task" "permission denied" \
  "SET SESSION AUTHORIZATION factory_rt_tradix; INSERT INTO factory.tasks (project_id,task_key,title,request_text,acceptance_criteria,risk_class,approval_required) VALUES ('11111111-1111-4111-8111-111111111111','runtime-direct-task','forbidden','forbidden',jsonb_build_array('x'),'low',false)"
expect_failure "runtime cannot directly create an attempt" "permission denied" \
  "SET SESSION AUTHORIZATION factory_rt_tradix; INSERT INTO factory.task_attempts (task_id,attempt_number,worker_role) VALUES ('aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',99,'implementer')"
expect_failure "runtime cannot directly create artifacts" "permission denied" \
  "SET SESSION AUTHORIZATION factory_rt_tradix; INSERT INTO factory.task_artifacts (task_id,attempt_id,artifact_type,object_uri,sha256,byte_size) VALUES ('aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa','cccccccc-cccc-4ccc-8ccc-cccccccccccc','x','ci://direct-write','aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',0)"
expect_failure "runtime cannot directly create evidence" "permission denied" \
  "SET SESSION AUTHORIZATION factory_rt_tradix; INSERT INTO factory.task_evidence (task_id,attempt_id,artifact_id,evidence_type,recorded_by) VALUES ('aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa','cccccccc-cccc-4ccc-8ccc-cccccccccccc','88888888-8888-4888-8888-888888888888','x','forged')"

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


# Product dossier snapshots are versioned, project-scoped, idempotent, and append-only.
dossier_v1='{"schema_version":1,"product_type":"software","mission":"TRADIX dossier isolation test","requirements":["independent product record"],"acceptance_criteria":["versioned and isolated"],"lifecycle":{"state":"active"}}'
dossier_v2='{"schema_version":1,"product_type":"software","mission":"TRADIX dossier revision two","requirements":["independent product record","revision history"],"acceptance_criteria":["versioned and isolated"],"lifecycle":{"state":"active"}}'

first_dossier_version=$(psql -qAt -c "SET SESSION AUTHORIZATION factory_rt_tradix; SELECT factory.record_product_dossier('11111111-1111-4111-8111-111111111111', '$dossier_v1'::jsonb, 'tradix-dossier-v1'); RESET SESSION AUTHORIZATION")
retry_dossier_version=$(psql -qAt -c "SET SESSION AUTHORIZATION factory_rt_tradix; SELECT factory.record_product_dossier('11111111-1111-4111-8111-111111111111', '$dossier_v1'::jsonb, 'tradix-dossier-v1'); RESET SESSION AUTHORIZATION")
second_dossier_version=$(psql -qAt -c "SET SESSION AUTHORIZATION factory_rt_tradix; SELECT factory.record_product_dossier('11111111-1111-4111-8111-111111111111', '$dossier_v2'::jsonb, 'tradix-dossier-v2'); RESET SESSION AUTHORIZATION")
if [[ "$first_dossier_version" != "1" || "$retry_dossier_version" != "1" || "$second_dossier_version" != "2" ]]; then
  echo "FAIL: product dossier versioning or idempotent retry is incorrect"
  exit 1
fi
echo "PASS: product dossier snapshots are versioned and idempotent"

physical_dossier='{"schema_version":1,"product_type":"physical","mission":"Independent physical product dossier","requirements":["no Git repository required"],"acceptance_criteria":["physical product dossier can be versioned"],"lifecycle":{"state":"active"},"resource_plan":{"equipment":[]}}'
physical_version=$(psql -qAt -c "SET SESSION AUTHORIZATION factory_rt_physical_goods; SELECT factory.record_product_dossier('44444444-4444-4444-8444-444444444444', '$physical_dossier'::jsonb, 'physical-dossier-v1'); RESET SESSION AUTHORIZATION")
if [[ "$physical_version" != "1" ]]; then
  echo "FAIL: physical product without a Git repository could not receive its own dossier"
  exit 1
fi
if [[ "$(psql -qAt -c "SET SESSION AUTHORIZATION factory_rt_physical_goods; SELECT count(*) FROM factory.product_dossier_versions; RESET SESSION AUTHORIZATION")" != "1" ]]; then
  echo "FAIL: physical product cannot read its own dossier"
  exit 1
fi
if [[ "$(psql -qAt -c "SET SESSION AUTHORIZATION factory_rt_tradix; SELECT count(*) FROM factory.product_dossier_versions; RESET SESSION AUTHORIZATION")" != "2" ]]; then
  echo "FAIL: TRADIX dossier visibility was contaminated by another product"
  exit 1
fi
echo "PASS: physical product dossier creation and cross-product isolation"


expect_failure "runtime cannot write a dossier for another project" "not authorized for this product dossier" \
  "SET SESSION AUTHORIZATION factory_rt_tradix; SELECT factory.record_product_dossier('22222222-2222-4222-8222-222222222222', '$dossier_v1'::jsonb, 'cross-project-dossier')"
expect_failure "dossier product type must match its registered product" "dossier product_type does not match the registered product" \
  "SET SESSION AUTHORIZATION factory_rt_tradix; SELECT factory.record_product_dossier('11111111-1111-4111-8111-111111111111', '{\"schema_version\":1,\"product_type\":\"physical\",\"mission\":\"wrong type\",\"requirements\":[\"x\"],\"acceptance_criteria\":[\"y\"],\"lifecycle\":{}}'::jsonb, 'wrong-product-type')"
expect_failure "dossier must include required minimum fields" "product dossier does not satisfy the minimum schema" \
  "SET SESSION AUTHORIZATION factory_rt_tradix; SELECT factory.record_product_dossier('11111111-1111-4111-8111-111111111111', '{\"schema_version\":1,\"product_type\":\"software\",\"requirements\":[\"x\"],\"acceptance_criteria\":[\"y\"],\"lifecycle\":{}}'::jsonb, 'missing-mission')"

if [[ "$(psql -qAt -c "SET SESSION AUTHORIZATION factory_rt_tradix; SELECT count(*) FROM factory.product_dossier_versions; RESET SESSION AUTHORIZATION")" != "2" ]]; then
  echo "FAIL: TRADIX runtime cannot read its own dossier versions"
  exit 1
fi
if [[ "$(psql -qAt -c "SET SESSION AUTHORIZATION factory_rt_info_engine; SELECT count(*) FROM factory.product_dossier_versions; RESET SESSION AUTHORIZATION")" != "0" ]]; then
  echo "FAIL: info_engine runtime can read TRADIX dossier versions"
  exit 1
fi
expect_failure "product dossier snapshots reject UPDATE" "Rows in factory.product_dossier_versions are append-only" \
  "UPDATE factory.product_dossier_versions SET dossier = '{}'::jsonb WHERE project_id = '11111111-1111-4111-8111-111111111111' AND version_no = 1"
expect_failure "product dossier snapshots reject DELETE" "Rows in factory.product_dossier_versions are append-only" \
  "DELETE FROM factory.product_dossier_versions WHERE project_id = '11111111-1111-4111-8111-111111111111' AND version_no = 1"
expect_failure "product dossier snapshots reject TRUNCATE" "Rows in factory.product_dossier_versions are append-only" \
  "TRUNCATE factory.product_dossier_versions, factory.intake_approvals"
expect_failure "runtime cannot directly insert a dossier snapshot" "permission denied" \
  "SET SESSION AUTHORIZATION factory_rt_tradix; INSERT INTO factory.product_dossier_versions (project_id,version_no,idempotency_key,dossier,created_by_login) VALUES ('11111111-1111-4111-8111-111111111111',99,'direct-write','{}'::jsonb,'factory_rt_tradix')"


# The machine-readable dossier contract must remain aligned with the database envelope.
node --input-type=module <<'NODE'
import { readFileSync } from "node:fs";
const schema = JSON.parse(readFileSync("schemas/product-dossier-v1.schema.json", "utf8"));
const expected = ["schema_version", "product_type", "mission", "requirements", "acceptance_criteria", "lifecycle"];
if (schema.$schema !== "https://json-schema.org/draft/2020-12/schema") throw new Error("wrong JSON Schema draft");
if (schema.properties?.schema_version?.const !== 1) throw new Error("schema_version must be 1");
for (const key of expected) {
  if (!schema.required?.includes(key) || !schema.properties?.[key]) throw new Error(`missing required dossier field: ${key}`);
}
if (schema.additionalProperties !== true) throw new Error("product-specific dossier fields must remain extensible");
for (const key of ["decisions", "resource_plan", "budget", "costs", "deliverables", "risks", "assets", "dependencies", "domain_specification"]) {
  if (!schema.properties[key]) throw new Error(`missing extensible product section: ${key}`);
}
const physicalProduct = {
  schema_version: 1,
  product_type: "physical",
  mission: "A physical product dossier fixture",
  requirements: ["independent product record"],
  acceptance_criteria: ["versioned and isolated"],
  lifecycle: { state: "active" },
  resource_plan: { equipment: [] }
};
for (const key of schema.required) if (!(key in physicalProduct)) throw new Error(`fixture missing ${key}`);
if (physicalProduct.product_type !== "physical") throw new Error("physical product fixture invalid");
console.log("PASS: product dossier JSON Schema v1 is valid and supports non-software products");
NODE


# Mission and task-plan snapshots are immutable, versioned, idempotent and product-scoped.
mission_v1='{"mission_id":"tradix-foundation","project_key":"tradix","version":1,"title":"TRADIX foundation","objective":"Establish a durable product factory core.","acceptance_criteria":["Mission history is durable"],"constraints":["Do not touch Production"],"risk_class":"low","approval_required":false}'
mission_v2='{"mission_id":"tradix-foundation","project_key":"tradix","version":2,"title":"TRADIX foundation revision","objective":"Establish a durable and auditable product factory core.","acceptance_criteria":["Mission history is durable","Versions are immutable"],"constraints":["Do not touch Production"],"risk_class":"low","approval_required":false}'
mission_first=$(psql -qAt -c "SET SESSION AUTHORIZATION factory_rt_tradix; SELECT factory.record_mission_version('11111111-1111-4111-8111-111111111111', '$mission_v1'::jsonb, 'tradix-mission-v1'); RESET SESSION AUTHORIZATION")
mission_retry=$(psql -qAt -c "SET SESSION AUTHORIZATION factory_rt_tradix; SELECT factory.record_mission_version('11111111-1111-4111-8111-111111111111', '$mission_v1'::jsonb, 'tradix-mission-v1'); RESET SESSION AUTHORIZATION")
mission_second=$(psql -qAt -c "SET SESSION AUTHORIZATION factory_rt_tradix; SELECT factory.record_mission_version('11111111-1111-4111-8111-111111111111', '$mission_v2'::jsonb, 'tradix-mission-v2'); RESET SESSION AUTHORIZATION")
if [[ "$mission_first" != "1" || "$mission_retry" != "1" || "$mission_second" != "2" ]]; then
  echo "FAIL: mission versioning or idempotent retry is incorrect"
  exit 1
fi
echo "PASS: mission snapshots are versioned and idempotent"

plan_v1='{"mission_id":"tradix-foundation","mission_version":1,"plan_version":1,"project_key":"tradix","tasks":[{"task_id":"specify-core","project_key":"tradix","title":"Specify core","request":"Define core boundaries.","acceptance_criteria":["Specification exists"],"risk_class":"low","approval_required":false},{"task_id":"test-core","project_key":"tradix","title":"Test core","request":"Test core invariants.","acceptance_criteria":["Tests pass"],"risk_class":"low","approval_required":false}],"dependencies":[{"depends_on":"specify-core","task_id":"test-core"}]}'
plan_first=$(psql -qAt -c "SET SESSION AUTHORIZATION factory_rt_tradix; SELECT factory.record_task_plan_version('11111111-1111-4111-8111-111111111111','tradix-foundation',1,'$plan_v1'::jsonb,'tradix-plan-v1'); RESET SESSION AUTHORIZATION")
plan_retry=$(psql -qAt -c "SET SESSION AUTHORIZATION factory_rt_tradix; SELECT factory.record_task_plan_version('11111111-1111-4111-8111-111111111111','tradix-foundation',1,'$plan_v1'::jsonb,'tradix-plan-v1'); RESET SESSION AUTHORIZATION")
plan_v2='{"mission_id":"tradix-foundation","mission_version":2,"plan_version":2,"project_key":"tradix","tasks":[{"task_id":"specify-core","project_key":"tradix","title":"Specify core","request":"Define core boundaries and controls.","acceptance_criteria":["Specification exists"],"risk_class":"low","approval_required":false}],"dependencies":[]}'
plan_second=$(psql -qAt -c "SET SESSION AUTHORIZATION factory_rt_tradix; SELECT factory.record_task_plan_version('11111111-1111-4111-8111-111111111111','tradix-foundation',2,'$plan_v2'::jsonb,'tradix-plan-v2'); RESET SESSION AUTHORIZATION")
if [[ "$plan_first" != "1" || "$plan_retry" != "1" || "$plan_second" != "2" ]]; then
  echo "FAIL: task-plan versioning or idempotent retry is incorrect"
  exit 1
fi
echo "PASS: task-plan snapshots are versioned and idempotent"

expect_failure "mission idempotency key rejects changed content" "mission idempotency key reused with different content" \
  "SET SESSION AUTHORIZATION factory_rt_tradix; SELECT factory.record_mission_version('11111111-1111-4111-8111-111111111111', '$mission_v2'::jsonb, 'tradix-mission-v1')"
expect_failure "mission versions must be monotonic" "mission version must equal the next stored version" \
  "SET SESSION AUTHORIZATION factory_rt_tradix; SELECT factory.record_mission_version('11111111-1111-4111-8111-111111111111', '{\"mission_id\":\"tradix-foundation\",\"project_key\":\"tradix\",\"version\":4,\"title\":\"Gap\",\"objective\":\"No skipped versions\",\"acceptance_criteria\":[\"reject gap\"],\"risk_class\":\"low\",\"approval_required\":false}'::jsonb, 'tradix-mission-gap')"
expect_failure "task plan idempotency key rejects changed content" "task plan idempotency key reused with different content" \
  "SET SESSION AUTHORIZATION factory_rt_tradix; SELECT factory.record_task_plan_version('11111111-1111-4111-8111-111111111111','tradix-foundation',2,'$plan_v2'::jsonb,'tradix-plan-v1')"
expect_failure "task plan rejects cyclic dependency graph" "task plan dependency graph contains a cycle" \
  "SET SESSION AUTHORIZATION factory_rt_tradix; SELECT factory.record_task_plan_version('11111111-1111-4111-8111-111111111111','tradix-foundation',1,'{\"mission_id\":\"tradix-foundation\",\"mission_version\":1,\"plan_version\":3,\"project_key\":\"tradix\",\"tasks\":[{\"task_id\":\"a\",\"project_key\":\"tradix\"},{\"task_id\":\"b\",\"project_key\":\"tradix\"}],\"dependencies\":[{\"depends_on\":\"a\",\"task_id\":\"b\"},{\"depends_on\":\"b\",\"task_id\":\"a\"}]}'::jsonb,'tradix-plan-cycle')"
expect_failure "runtime cannot write a mission for another product" "not authorized for this product mission" \
  "SET SESSION AUTHORIZATION factory_rt_tradix; SELECT factory.record_mission_version('22222222-2222-4222-8222-222222222222', '{\"mission_id\":\"other\",\"project_key\":\"info-engine\",\"version\":1,\"title\":\"Other\",\"objective\":\"Cross-project write\",\"acceptance_criteria\":[\"reject\"],\"risk_class\":\"low\",\"approval_required\":false}'::jsonb, 'cross-project-mission')"
expect_failure "runtime cannot directly insert a mission snapshot" "permission denied" \
  "SET SESSION AUTHORIZATION factory_rt_tradix; INSERT INTO factory.mission_versions (project_id,mission_id,version_no,idempotency_key,mission,created_by_login) VALUES ('11111111-1111-4111-8111-111111111111','bypass',99,'direct-mission','{}'::jsonb,'factory_rt_tradix')"
expect_failure "mission snapshots reject UPDATE" "Rows in factory.mission_versions are append-only" \
  "UPDATE factory.mission_versions SET mission = '{}'::jsonb WHERE project_id = '11111111-1111-4111-8111-111111111111' AND mission_id = 'tradix-foundation' AND version_no = 1"
expect_failure "mission snapshots reject DELETE" "Rows in factory.mission_versions are append-only" \
  "DELETE FROM factory.mission_versions WHERE project_id = '11111111-1111-4111-8111-111111111111' AND mission_id = 'tradix-foundation' AND version_no = 1"
expect_failure "mission snapshots reject TRUNCATE" "append-only" \
  "TRUNCATE factory.mission_versions, factory.task_plan_versions, factory.intake_approvals"
expect_failure "task-plan snapshots reject UPDATE" "Rows in factory.task_plan_versions are append-only" \
  "UPDATE factory.task_plan_versions SET task_plan = '{}'::jsonb WHERE project_id = '11111111-1111-4111-8111-111111111111' AND mission_id = 'tradix-foundation' AND plan_version_no = 1"
expect_failure "task-plan snapshots reject DELETE" "Rows in factory.task_plan_versions are append-only" \
  "DELETE FROM factory.task_plan_versions WHERE project_id = '11111111-1111-4111-8111-111111111111' AND mission_id = 'tradix-foundation' AND plan_version_no = 1"
expect_failure "task-plan snapshots reject TRUNCATE" "Rows in factory.task_plan_versions are append-only" \
  "TRUNCATE factory.task_plan_versions, factory.intake_approvals"

physical_mission='{"mission_id":"press-line","project_key":"physical-goods","version":1,"title":"Press line","objective":"Prepare a physical production line.","acceptance_criteria":["Equipment plan recorded"],"risk_class":"low","approval_required":false}'
physical_mission_version=$(psql -qAt -c "SET SESSION AUTHORIZATION factory_rt_physical_goods; SELECT factory.record_mission_version('44444444-4444-4444-8444-444444444444', '$physical_mission'::jsonb, 'physical-mission-v1'); RESET SESSION AUTHORIZATION")
if [[ "$physical_mission_version" != "1" ]]; then
  echo "FAIL: repository-free physical product could not store its mission"
  exit 1
fi
if [[ "$(psql -qAt -c "SET SESSION AUTHORIZATION factory_rt_info_engine; SELECT count(*) FROM factory.mission_versions; RESET SESSION AUTHORIZATION")" != "0" ]]; then
  echo "FAIL: info_engine can read another product's mission snapshots"
  exit 1
fi
if [[ "$(psql -qAt -c "SET SESSION AUTHORIZATION factory_rt_tradix; SELECT count(*) FROM factory.mission_versions; RESET SESSION AUTHORIZATION")" != "2" ]]; then
  echo "FAIL: TRADIX mission visibility is not isolated"
  exit 1
fi
if [[ "$(psql -qAt -c "SET SESSION AUTHORIZATION factory_rt_tradix; SELECT count(*) FROM factory.task_plan_versions; RESET SESSION AUTHORIZATION")" != "2" ]]; then
  echo "FAIL: TRADIX task-plan visibility is not isolated"
  exit 1
fi
echo "PASS: physical and software product mission storage remains isolated"


# Product intake decisions bind one approver login to one exact immutable snapshot set.
pending_dossier_v1='{"schema_version":1,"product_type":"software","mission":"Approval-gated intake v1","requirements":["review before execution"],"acceptance_criteria":["decision is bound to exact versions"],"lifecycle":{"state":"pending_approval"}}'
pending_dossier_v2='{"schema_version":1,"product_type":"software","mission":"Approval-gated intake v2","requirements":["review revised scope before execution"],"acceptance_criteria":["decision is bound to exact versions"],"lifecycle":{"state":"pending_approval"}}'
intake_mission_v1='{"mission_id":"tradix-intake-approval","project_key":"tradix","version":1,"title":"Approval-gated intake v1","objective":"Prove an approval decision is bound to immutable snapshots.","acceptance_criteria":["Decision records exact snapshot versions"],"constraints":["No dispatch"],"risk_class":"low","approval_required":true}'
intake_mission_v2='{"mission_id":"tradix-intake-approval","project_key":"tradix","version":2,"title":"Approval-gated intake v2","objective":"Prove a revised intake needs a new decision.","acceptance_criteria":["Decision records exact snapshot versions"],"constraints":["No dispatch"],"risk_class":"low","approval_required":true}'
intake_plan_v1='{"mission_id":"tradix-intake-approval","mission_version":1,"plan_version":1,"project_key":"tradix","tasks":[{"task_id":"review-v1","project_key":"tradix","title":"Review v1","request":"Review the exact intake v1.","acceptance_criteria":["Review complete"],"risk_class":"low","approval_required":true}],"dependencies":[]}'
intake_plan_v2='{"mission_id":"tradix-intake-approval","mission_version":2,"plan_version":2,"project_key":"tradix","tasks":[{"task_id":"review-v2","project_key":"tradix","title":"Review v2","request":"Review the exact intake v2.","acceptance_criteria":["Review complete"],"risk_class":"low","approval_required":true}],"dependencies":[]}'

dossier_v3=$(psql -qAt -c "SET SESSION AUTHORIZATION factory_rt_tradix; SELECT factory.record_product_dossier('11111111-1111-4111-8111-111111111111', '$pending_dossier_v1'::jsonb, 'tradix-intake-dossier-v1'); RESET SESSION AUTHORIZATION")
dossier_v4=$(psql -qAt -c "SET SESSION AUTHORIZATION factory_rt_tradix; SELECT factory.record_product_dossier('11111111-1111-4111-8111-111111111111', '$pending_dossier_v2'::jsonb, 'tradix-intake-dossier-v2'); RESET SESSION AUTHORIZATION")
intake_mission_1=$(psql -qAt -c "SET SESSION AUTHORIZATION factory_rt_tradix; SELECT factory.record_mission_version('11111111-1111-4111-8111-111111111111', '$intake_mission_v1'::jsonb, 'tradix-intake-mission-v1'); RESET SESSION AUTHORIZATION")
intake_mission_2=$(psql -qAt -c "SET SESSION AUTHORIZATION factory_rt_tradix; SELECT factory.record_mission_version('11111111-1111-4111-8111-111111111111', '$intake_mission_v2'::jsonb, 'tradix-intake-mission-v2'); RESET SESSION AUTHORIZATION")
intake_plan_1=$(psql -qAt -c "SET SESSION AUTHORIZATION factory_rt_tradix; SELECT factory.record_task_plan_version('11111111-1111-4111-8111-111111111111','tradix-intake-approval',1,'$intake_plan_v1'::jsonb,'tradix-intake-plan-v1'); RESET SESSION AUTHORIZATION")
intake_plan_2=$(psql -qAt -c "SET SESSION AUTHORIZATION factory_rt_tradix; SELECT factory.record_task_plan_version('11111111-1111-4111-8111-111111111111','tradix-intake-approval',2,'$intake_plan_v2'::jsonb,'tradix-intake-plan-v2'); RESET SESSION AUTHORIZATION")
if [[ "$dossier_v3" != "3" || "$dossier_v4" != "4" || "$intake_mission_1" != "1" || "$intake_mission_2" != "2" || "$intake_plan_1" != "1" || "$intake_plan_2" != "2" ]]; then
  echo "FAIL: approval snapshot fixtures were not versioned as expected"
  exit 1
fi

rejected_approval=$(psql -qAt -c "SET SESSION AUTHORIZATION factory_approver_tradix; SELECT factory.record_intake_approval('tradix-intake-approval',3,1,1,'rejected','Scope needs revision','tradix-intake-decision-v1'); RESET SESSION AUTHORIZATION")
rejected_retry=$(psql -qAt -c "SET SESSION AUTHORIZATION factory_approver_tradix; SELECT factory.record_intake_approval('tradix-intake-approval',3,1,1,'rejected','Scope needs revision','tradix-intake-decision-v1'); RESET SESSION AUTHORIZATION")
if [[ -z "$rejected_approval" || "$rejected_approval" != "$rejected_retry" ]]; then
  echo "FAIL: approval decision retry was not idempotent"
  exit 1
fi
if [[ "$(psql -qAt -c "SELECT decision || ':' || decided_by_login::text || ':' || dossier_version_no::text || ':' || mission_version_no::text || ':' || plan_version_no::text FROM factory.intake_approvals WHERE approval_id='$rejected_approval'")" != "rejected:factory_approver_tradix:3:1:1" ]]; then
  echo "FAIL: rejection audit did not capture the authentic approval login and exact versions"
  exit 1
fi
echo "PASS: intake rejection is immutable, version-bound, and idempotent"

approved_approval=$(psql -qAt -c "SET SESSION AUTHORIZATION factory_approver_tradix; SELECT factory.record_intake_approval('tradix-intake-approval',4,2,2,'approved','Reviewed exact revised scope','tradix-intake-decision-v2'); RESET SESSION AUTHORIZATION")
if [[ -z "$approved_approval" ]]; then
  echo "FAIL: revised intake approval was not recorded"
  exit 1
fi
if [[ "$(psql -qAt -c "SELECT decision || ':' || decided_by_login::text || ':' || dossier_version_no::text || ':' || mission_version_no::text || ':' || plan_version_no::text FROM factory.intake_approvals WHERE approval_id='$approved_approval'")" != "approved:factory_approver_tradix:4:2:2" ]]; then
  echo "FAIL: approval audit did not bind the exact revised snapshot versions"
  exit 1
fi
expect_failure "one snapshot set cannot receive a second final decision" "this exact intake snapshot set already has a final decision" \
  "SET SESSION AUTHORIZATION factory_approver_tradix; SELECT factory.record_intake_approval('tradix-intake-approval',4,2,2,'rejected','Try to reverse an immutable decision','tradix-intake-decision-v2-reverse')"
expect_failure "approval idempotency key cannot be reused for different intent" "intake approval idempotency key reused with different intent" \
  "SET SESSION AUTHORIZATION factory_approver_tradix; SELECT factory.record_intake_approval('tradix-intake-approval',4,2,2,'rejected','Changed decision','tradix-intake-decision-v2')"
expect_failure "active dossier cannot be approved as a pending intake" "snapshot set is not an approval-gated intake" \
  "SET SESSION AUTHORIZATION factory_approver_tradix; SELECT factory.record_intake_approval('tradix-foundation',1,1,1,'approved','Not pending approval','tradix-active-dossier-approval')"
expect_failure "runtime cannot invoke the intake approval function" "permission denied for function record_intake_approval" \
  "SET SESSION AUTHORIZATION factory_rt_tradix; SELECT factory.record_intake_approval('tradix-intake-approval',4,2,2,'approved','Forged runtime approval','tradix-runtime-forged-approval')"
expect_failure "approval identity cannot directly insert intake decisions" "permission denied" \
  "SET SESSION AUTHORIZATION factory_approver_tradix; INSERT INTO factory.intake_approvals (project_id,mission_id,dossier_version_no,mission_version_no,plan_version_no,decision,rationale,idempotency_key,decided_by_login) VALUES ('11111111-1111-4111-8111-111111111111','tradix-intake-approval',4,2,2,'approved','direct insert','direct-approval-write','factory_approver_tradix')"
expect_failure "runtime cannot directly insert intake decisions" "permission denied" \
  "SET SESSION AUTHORIZATION factory_rt_tradix; INSERT INTO factory.intake_approvals (project_id,mission_id,dossier_version_no,mission_version_no,plan_version_no,decision,rationale,idempotency_key,decided_by_login) VALUES ('11111111-1111-4111-8111-111111111111','tradix-intake-approval',4,2,2,'approved','direct insert','runtime-direct-approval','factory_rt_tradix')"
expect_failure "intake approval records reject UPDATE" "Rows in factory.intake_approvals are append-only" \
  "UPDATE factory.intake_approvals SET rationale='tampered' WHERE approval_id='$approved_approval'"
expect_failure "intake approval records reject DELETE" "Rows in factory.intake_approvals are append-only" \
  "DELETE FROM factory.intake_approvals WHERE approval_id='$approved_approval'"
expect_failure "intake approval records reject TRUNCATE" "Rows in factory.intake_approvals are append-only" \
  "TRUNCATE factory.intake_approvals"
if [[ "$(psql -qAt -c "SET SESSION AUTHORIZATION factory_rt_info_engine; SELECT count(*) FROM factory.intake_approvals; RESET SESSION AUTHORIZATION")" != "0" ]]; then
  echo "FAIL: another product runtime can read TRADIX intake approvals"
  exit 1
fi
echo "PASS: approval authority is separate, project-isolated, and cannot be forged by runtime"


echo "All factory ledger SQL integration checks passed."
