#!/usr/bin/env bash
set -euo pipefail
container_id="${1:?postgres container id required}"
psql_exec() {
  docker exec -i "$container_id" psql -X -v ON_ERROR_STOP=1 -U postgres -d tradix_test "$@"
}

psql_exec <<'SQL'
INSERT INTO memory_projects (project_key, name)
VALUES ('tradix', 'TRADIX');

INSERT INTO memory_missions (project_id, mission_key, title, objective)
SELECT project_id, 'runtime-mvp', 'Runtime MVP', 'Verify persistent memory retrieval'
FROM memory_projects WHERE project_key = 'tradix';

INSERT INTO memory_events (
  project_id, event_type, actor_id, idempotency_key, payload, occurred_at
)
SELECT project_id, 'CI_INTEGRATION_TEST', 'github-actions',
       'memory-gateway-ci-001', '{"verified":true}'::jsonb, now()
FROM memory_projects WHERE project_key = 'tradix';

DO $$
BEGIN
  IF (SELECT count(*) FROM memory_projects) <> 1 THEN
    RAISE EXCEPTION 'project seed failed';
  END IF;
  IF (SELECT count(*) FROM memory_missions) <> 1 THEN
    RAISE EXCEPTION 'mission seed failed';
  END IF;
  IF (SELECT count(*) FROM memory_events) <> 1 THEN
    RAISE EXCEPTION 'event seed failed';
  END IF;
  IF memory_bootstrap_context('tradix')->'project'->>'project_key' <> 'tradix' THEN
    RAISE EXCEPTION 'bootstrap context returned wrong project';
  END IF;
END $$;

SQL

if psql_exec -c "UPDATE memory_events SET event_type='MUTATED' WHERE idempotency_key='memory-gateway-ci-001'" >/dev/null 2>&1; then
  echo "append-only UPDATE unexpectedly succeeded" >&2
  exit 1
fi
if psql_exec -c "DELETE FROM memory_events WHERE idempotency_key='memory-gateway-ci-001'" >/dev/null 2>&1; then
  echo "append-only DELETE unexpectedly succeeded" >&2
  exit 1
fi
if psql_exec -c "INSERT INTO memory_events (project_id,event_type,actor_id,idempotency_key,payload,occurred_at) SELECT project_id,'DUPLICATE','ci','memory-gateway-ci-001','{}',now() FROM memory_projects WHERE project_key='tradix'" >/dev/null 2>&1; then
  echo "duplicate idempotency key unexpectedly succeeded" >&2
  exit 1
fi

echo "memory gateway SQL: schema, bootstrap, append-only, and idempotency checks passed"
