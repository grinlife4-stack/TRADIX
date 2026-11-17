#!/usr/bin/env bash
set -euo pipefail
container_id="${1:?postgres container id required}"
psql_exec() {
  docker exec -i "$container_id" psql -X -v ON_ERROR_STOP=1 -U postgres -d tradix_test "$@"
}

psql_exec <<'SQL'
INSERT INTO memory_projects (project_key, name)
VALUES ('tradix', 'TRADIX'), ('other-project', 'Other Project');

INSERT INTO memory_missions (project_id, mission_key, title, objective)
SELECT project_id, 'runtime-mvp', 'Runtime MVP', 'Verify persistent memory retrieval'
FROM memory_projects WHERE project_key = 'tradix';

INSERT INTO memory_events (
  project_id, event_type, actor_id, idempotency_key, payload, occurred_at
)
SELECT project_id, 'CI_INTEGRATION_TEST', 'github-actions',
       'memory-gateway-ci-001', '{"verified":true}'::jsonb, now()
FROM memory_projects WHERE project_key = 'tradix';

INSERT INTO memory_gateway_tokens(project_id, token_hash)
SELECT project_id, decode('1033fb9607c4fb10b39df080baf1f1b2c8aa0c3de777d279d9f10b506369512f','hex')
FROM memory_projects WHERE project_key='tradix';
INSERT INTO memory_gateway_tokens(project_id, token_hash)
SELECT project_id, decode('1bc2479c6e54b8ea89ba43fea4e60c8a6cb3c1ce12f651a7dd2998e0270f6d2b','hex')
FROM memory_projects WHERE project_key='other-project';
INSERT INTO memory_gateway_tokens(project_id, token_hash, revoked_at)
SELECT project_id, decode('3227b49cb5c69320c01d0ac00e76e5602f97608c825c7311e850b6decc82f7c3','hex'), now()
FROM memory_projects WHERE project_key='tradix';

DO $$
BEGIN
  IF (SELECT count(*) FROM memory_projects) <> 2 THEN RAISE EXCEPTION 'project seed failed'; END IF;
  IF (SELECT count(*) FROM memory_missions) <> 1 THEN RAISE EXCEPTION 'mission seed failed'; END IF;
  IF (SELECT count(*) FROM memory_events) <> 1 THEN RAISE EXCEPTION 'event seed failed'; END IF;
  IF memory_bootstrap_context('tradix')->'project'->>'project_key' <> 'tradix' THEN
    RAISE EXCEPTION 'bootstrap context returned wrong project';
  END IF;
END $$;
SQL

if docker exec -i "$container_id" psql -X -v ON_ERROR_STOP=1 -U postgres -d tradix_test -c "UPDATE memory_events SET event_type='MUTATED' WHERE idempotency_key='memory-gateway-ci-001'" >/dev/null 2>&1; then
  echo "append-only UPDATE unexpectedly succeeded" >&2; exit 1
fi
if docker exec -i "$container_id" psql -X -v ON_ERROR_STOP=1 -U postgres -d tradix_test -c "DELETE FROM memory_events WHERE idempotency_key='memory-gateway-ci-001'" >/dev/null 2>&1; then
  echo "append-only DELETE unexpectedly succeeded" >&2; exit 1
fi
if docker exec -i "$container_id" psql -X -v ON_ERROR_STOP=1 -U postgres -d tradix_test -c "INSERT INTO memory_events (project_id,event_type,actor_id,idempotency_key,payload,occurred_at) SELECT project_id,'DUPLICATE','ci','memory-gateway-ci-001','{}',now() FROM memory_projects WHERE project_key='tradix'" >/dev/null 2>&1; then
  echo "duplicate idempotency key unexpectedly succeeded" >&2; exit 1
fi

if docker exec -e PGPASSWORD=ci-only-memory-gateway-password -i "$container_id" psql -X -v ON_ERROR_STOP=1 -U memory_gateway_ci -d tradix_test -c "SELECT * FROM public.memory_projects" >/dev/null 2>&1; then
  echo "runtime login unexpectedly read project table directly" >&2; exit 1
fi
result=$(docker exec -e PGPASSWORD=ci-only-memory-gateway-password -i "$container_id" psql -X -qAt -v ON_ERROR_STOP=1 -U memory_gateway_ci -d tradix_test -c "SELECT public.memory_bootstrap_context_for_token(decode('1033fb9607c4fb10b39df080baf1f1b2c8aa0c3de777d279d9f10b506369512f','hex'))->'project'->>'project_key'")
test "$result" = "tradix" || { echo "runtime token lookup failed: $result"; exit 1; }

echo "memory gateway SQL: project scope, least privilege, append-only, and token checks passed"
