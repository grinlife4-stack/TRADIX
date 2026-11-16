-- DRAFT ONLY — CI applies this to disposable PostgreSQL 17.
-- Adds immutable, project-scoped mission and task-plan snapshots.
BEGIN;

CREATE TABLE factory.mission_versions (
    mission_version_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES factory.projects(project_id) ON DELETE RESTRICT,
    mission_id TEXT NOT NULL CHECK (length(trim(mission_id)) BETWEEN 1 AND 80),
    version_no INTEGER NOT NULL CHECK (version_no > 0),
    idempotency_key TEXT NOT NULL CHECK (length(trim(idempotency_key)) BETWEEN 1 AND 255),
    mission JSONB NOT NULL CHECK (jsonb_typeof(mission) = 'object'),
    created_by_login NAME NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (project_id, mission_id, version_no),
    UNIQUE (project_id, idempotency_key),
    UNIQUE (project_id, mission_id, version_no, mission_version_id)
);

CREATE INDEX mission_versions_latest_idx
    ON factory.mission_versions (project_id, mission_id, version_no DESC);

CREATE TABLE factory.task_plan_versions (
    task_plan_version_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL,
    mission_id TEXT NOT NULL,
    mission_version_no INTEGER NOT NULL CHECK (mission_version_no > 0),
    plan_version_no INTEGER NOT NULL CHECK (plan_version_no > 0),
    idempotency_key TEXT NOT NULL CHECK (length(trim(idempotency_key)) BETWEEN 1 AND 255),
    task_plan JSONB NOT NULL CHECK (jsonb_typeof(task_plan) = 'object'),
    created_by_login NAME NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (project_id, mission_id, plan_version_no),
    UNIQUE (project_id, idempotency_key),
    FOREIGN KEY (project_id, mission_id, mission_version_no)
        REFERENCES factory.mission_versions(project_id, mission_id, version_no)
        ON DELETE RESTRICT
);

CREATE INDEX task_plan_versions_latest_idx
    ON factory.task_plan_versions (project_id, mission_id, plan_version_no DESC);

CREATE FUNCTION factory.reject_mission_plan_mutation()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $immutable$
BEGIN
    RAISE EXCEPTION 'Rows in %.% are append-only', TG_TABLE_SCHEMA, TG_TABLE_NAME;
END;
$immutable$;

CREATE TRIGGER mission_versions_append_only
    BEFORE UPDATE OR DELETE ON factory.mission_versions
    FOR EACH ROW EXECUTE FUNCTION factory.reject_mission_plan_mutation();
CREATE TRIGGER mission_versions_no_truncate
    BEFORE TRUNCATE ON factory.mission_versions
    FOR EACH STATEMENT EXECUTE FUNCTION factory.reject_mission_plan_mutation();
CREATE TRIGGER task_plan_versions_append_only
    BEFORE UPDATE OR DELETE ON factory.task_plan_versions
    FOR EACH ROW EXECUTE FUNCTION factory.reject_mission_plan_mutation();
CREATE TRIGGER task_plan_versions_no_truncate
    BEFORE TRUNCATE ON factory.task_plan_versions
    FOR EACH STATEMENT EXECUTE FUNCTION factory.reject_mission_plan_mutation();

REVOKE UPDATE, DELETE, TRUNCATE ON factory.mission_versions FROM PUBLIC;
REVOKE UPDATE, DELETE, TRUNCATE ON factory.task_plan_versions FROM PUBLIC;

CREATE FUNCTION factory.record_mission_version(
    p_project_id UUID,
    p_mission JSONB,
    p_idempotency_key TEXT
)
RETURNS INTEGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, factory, pg_temp
AS $record_mission$
DECLARE
    v_project_key TEXT;
    v_mission_id TEXT;
    v_version INTEGER;
    v_existing factory.mission_versions%ROWTYPE;
BEGIN
    IF p_project_id IS NULL
       OR p_mission IS NULL OR jsonb_typeof(p_mission) <> 'object'
       OR p_idempotency_key IS NULL OR length(trim(p_idempotency_key)) NOT BETWEEN 1 AND 255
       OR jsonb_typeof(p_mission->'acceptance_criteria') <> 'array'
       OR jsonb_array_length(p_mission->'acceptance_criteria') NOT BETWEEN 1 AND 30
       OR jsonb_typeof(COALESCE(p_mission->'constraints', '[]'::jsonb)) <> 'array'
       OR COALESCE(jsonb_array_length(p_mission->'constraints'), 0) > 30
       OR p_mission->>'mission_id' IS NULL OR length(trim(p_mission->>'mission_id')) NOT BETWEEN 1 AND 80
       OR p_mission->>'project_key' IS NULL
       OR p_mission->>'version' !~ '^[1-9][0-9]*$'
       OR p_mission->>'title' IS NULL OR length(trim(p_mission->>'title')) NOT BETWEEN 1 AND 160
       OR p_mission->>'objective' IS NULL OR length(trim(p_mission->>'objective')) NOT BETWEEN 1 AND 12000
       OR COALESCE(p_mission->>'risk_class', 'low') NOT IN ('low','medium','high','critical')
       OR (COALESCE(p_mission->>'risk_class', 'low') IN ('high','critical')
           AND p_mission->>'approval_required' IS DISTINCT FROM 'true')
       OR ((p_mission ? 'budget_currency') <> (p_mission ? 'budget_limit_minor'))
       OR (p_mission ? 'budget_currency' AND p_mission->>'budget_currency' !~ '^[A-Z]{3}$')
       OR (p_mission ? 'budget_limit_minor' AND p_mission->>'budget_limit_minor' !~ '^(0|[1-9][0-9]*)$') THEN
        RAISE EXCEPTION 'invalid mission snapshot';
    END IF;

    IF NOT pg_catalog.pg_has_role(session_user, 'factory_runtime', 'MEMBER')
       OR pg_catalog.pg_has_role(session_user, 'factory_approval_authority', 'MEMBER')
       OR pg_catalog.pg_has_role(session_user, 'factory_executor_owner', 'MEMBER') THEN
        RAISE EXCEPTION 'session identity is not an isolated product runtime';
    END IF;

    SELECT project_key INTO v_project_key
    FROM factory.projects
    WHERE project_id = p_project_id;
    IF NOT FOUND OR NOT EXISTS (
        SELECT 1 FROM factory.project_identities
        WHERE role_name = session_user AND identity_kind = 'runtime'
          AND project_id = p_project_id
    ) THEN
        RAISE EXCEPTION 'not authorized for this product mission';
    END IF;
    IF p_mission->>'project_key' IS DISTINCT FROM v_project_key THEN
        RAISE EXCEPTION 'mission project_key does not match the registered product';
    END IF;
    v_mission_id := p_mission->>'mission_id';

    PERFORM pg_catalog.pg_advisory_xact_lock(
        pg_catalog.hashtextextended(p_project_id::text || ':mission:' || v_mission_id, 0)
    );

    SELECT * INTO v_existing FROM factory.mission_versions
    WHERE project_id = p_project_id AND idempotency_key = p_idempotency_key;
    IF FOUND THEN
        IF v_existing.mission_id = v_mission_id AND v_existing.mission = p_mission THEN
            RETURN v_existing.version_no;
        END IF;
        RAISE EXCEPTION 'mission idempotency key reused with different content';
    END IF;

    SELECT COALESCE(MAX(version_no), 0) + 1 INTO v_version
    FROM factory.mission_versions
    WHERE project_id = p_project_id AND mission_id = v_mission_id;
    IF (p_mission->>'version')::numeric <> v_version THEN
        RAISE EXCEPTION 'mission version must equal the next stored version';
    END IF;

    INSERT INTO factory.mission_versions (
        project_id, mission_id, version_no, idempotency_key, mission, created_by_login
    ) VALUES (
        p_project_id, v_mission_id, v_version, p_idempotency_key, p_mission, session_user
    );
    RETURN v_version;
END;
$record_mission$;

CREATE FUNCTION factory.record_task_plan_version(
    p_project_id UUID,
    p_mission_id TEXT,
    p_mission_version_no INTEGER,
    p_task_plan JSONB,
    p_idempotency_key TEXT
)
RETURNS INTEGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, factory, pg_temp
AS $record_plan$
DECLARE
    v_project_key TEXT;
    v_mission JSONB;
    v_version INTEGER;
    v_existing factory.task_plan_versions%ROWTYPE;
BEGIN
    IF p_project_id IS NULL
       OR p_mission_id IS NULL OR length(trim(p_mission_id)) NOT BETWEEN 1 AND 80
       OR p_mission_version_no IS NULL OR p_mission_version_no < 1
       OR p_task_plan IS NULL OR jsonb_typeof(p_task_plan) <> 'object'
       OR p_idempotency_key IS NULL OR length(trim(p_idempotency_key)) NOT BETWEEN 1 AND 255
       OR p_task_plan->>'mission_id' IS DISTINCT FROM p_mission_id
       OR p_task_plan->>'mission_version' !~ '^[1-9][0-9]*$'
       OR (p_task_plan->>'mission_version')::numeric <> p_mission_version_no
       OR p_task_plan->>'plan_version' !~ '^[1-9][0-9]*$'
       OR jsonb_typeof(p_task_plan->'tasks') <> 'array'
       OR jsonb_array_length(p_task_plan->'tasks') NOT BETWEEN 1 AND 100
       OR jsonb_typeof(p_task_plan->'dependencies') <> 'array'
       OR jsonb_array_length(p_task_plan->'dependencies') > 500 THEN
        RAISE EXCEPTION 'invalid task plan snapshot';
    END IF;

    IF NOT pg_catalog.pg_has_role(session_user, 'factory_runtime', 'MEMBER')
       OR pg_catalog.pg_has_role(session_user, 'factory_approval_authority', 'MEMBER')
       OR pg_catalog.pg_has_role(session_user, 'factory_executor_owner', 'MEMBER') THEN
        RAISE EXCEPTION 'session identity is not an isolated product runtime';
    END IF;

    SELECT p.project_key, m.mission
      INTO v_project_key, v_mission
    FROM factory.projects p
    JOIN factory.mission_versions m ON m.project_id = p.project_id
    WHERE p.project_id = p_project_id
      AND m.mission_id = p_mission_id
      AND m.version_no = p_mission_version_no
      AND EXISTS (
          SELECT 1 FROM factory.project_identities i
          WHERE i.role_name = session_user AND i.identity_kind = 'runtime'
            AND i.project_id = p_project_id
      );
    IF NOT FOUND THEN
        RAISE EXCEPTION 'mission version not found for this product runtime';
    END IF;
    IF p_task_plan->>'project_key' IS DISTINCT FROM v_project_key
       OR v_mission->>'project_key' IS DISTINCT FROM v_project_key
       OR v_mission->>'mission_id' IS DISTINCT FROM p_mission_id THEN
        RAISE EXCEPTION 'task plan project or mission identity mismatch';
    END IF;

    -- Database-level structural checks complement, but do not replace, the
    -- stricter Python contract validator. Reject malformed tasks and edges.
    IF EXISTS (
        SELECT 1 FROM jsonb_array_elements(p_task_plan->'tasks') t(value)
        WHERE jsonb_typeof(t.value) <> 'object'
           OR t.value->>'task_id' IS NULL
           OR length(trim(t.value->>'task_id')) NOT BETWEEN 1 AND 80
           OR t.value->>'project_key' IS DISTINCT FROM v_project_key
    ) OR (
        SELECT count(DISTINCT t.value->>'task_id')
        FROM jsonb_array_elements(p_task_plan->'tasks') t(value)
    ) <> jsonb_array_length(p_task_plan->'tasks') THEN
        RAISE EXCEPTION 'task plan contains malformed or duplicate task identities';
    END IF;

    IF EXISTS (
        SELECT 1
        FROM jsonb_array_elements(p_task_plan->'dependencies') d(value)
        WHERE jsonb_typeof(d.value) <> 'object'
           OR jsonb_object_length(d.value) <> 2
           OR d.value->>'depends_on' IS NULL
           OR d.value->>'task_id' IS NULL
           OR d.value->>'depends_on' = d.value->>'task_id'
           OR NOT EXISTS (
               SELECT 1 FROM jsonb_array_elements(p_task_plan->'tasks') t(value)
               WHERE t.value->>'task_id' = d.value->>'depends_on'
           )
           OR NOT EXISTS (
               SELECT 1 FROM jsonb_array_elements(p_task_plan->'tasks') t(value)
               WHERE t.value->>'task_id' = d.value->>'task_id'
           )
    ) OR (
        SELECT count(*) FROM jsonb_array_elements(p_task_plan->'dependencies')
    ) <> (
        SELECT count(DISTINCT (d.value->>'depends_on', d.value->>'task_id'))
        FROM jsonb_array_elements(p_task_plan->'dependencies') d(value)
    ) THEN
        RAISE EXCEPTION 'task plan contains malformed, duplicate, or unknown dependency edges';
    END IF;

    IF EXISTS (
        WITH RECURSIVE edges(src, dst) AS (
            SELECT d.value->>'depends_on', d.value->>'task_id'
            FROM jsonb_array_elements(p_task_plan->'dependencies') d(value)
        ),
        walk(start_id, node_id, path, cycle) AS (
            SELECT src, dst, ARRAY[src, dst], src = dst FROM edges
            UNION ALL
            SELECT w.start_id, e.dst, w.path || e.dst, e.dst = ANY(w.path)
            FROM walk w JOIN edges e ON e.src = w.node_id
            WHERE NOT w.cycle
        )
        SELECT 1 FROM walk WHERE cycle
    ) THEN
        RAISE EXCEPTION 'task plan dependency graph contains a cycle';
    END IF;

    PERFORM pg_catalog.pg_advisory_xact_lock(
        pg_catalog.hashtextextended(p_project_id::text || ':plan:' || p_mission_id, 0)
    );

    SELECT * INTO v_existing FROM factory.task_plan_versions
    WHERE project_id = p_project_id AND idempotency_key = p_idempotency_key;
    IF FOUND THEN
        IF v_existing.mission_id = p_mission_id
           AND v_existing.mission_version_no = p_mission_version_no
           AND v_existing.task_plan = p_task_plan THEN
            RETURN v_existing.plan_version_no;
        END IF;
        RAISE EXCEPTION 'task plan idempotency key reused with different content';
    END IF;

    SELECT COALESCE(MAX(plan_version_no), 0) + 1 INTO v_version
    FROM factory.task_plan_versions
    WHERE project_id = p_project_id AND mission_id = p_mission_id;
    IF (p_task_plan->>'plan_version')::numeric <> v_version THEN
        RAISE EXCEPTION 'plan_version must equal the next stored version';
    END IF;

    INSERT INTO factory.task_plan_versions (
        project_id, mission_id, mission_version_no, plan_version_no,
        idempotency_key, task_plan, created_by_login
    ) VALUES (
        p_project_id, p_mission_id, p_mission_version_no, v_version,
        p_idempotency_key, p_task_plan, session_user
    );
    RETURN v_version;
END;
$record_plan$;

ALTER TABLE factory.mission_versions ENABLE ROW LEVEL SECURITY;
ALTER TABLE factory.mission_versions FORCE ROW LEVEL SECURITY;
ALTER TABLE factory.task_plan_versions ENABLE ROW LEVEL SECURITY;
ALTER TABLE factory.task_plan_versions FORCE ROW LEVEL SECURITY;

CREATE POLICY mission_versions_isolated ON factory.mission_versions
    FOR SELECT TO PUBLIC
    USING (project_id IN (
        SELECT project_id FROM factory.project_identities
        WHERE role_name = session_user
    ));
CREATE POLICY mission_versions_insert ON factory.mission_versions
    FOR INSERT TO factory_executor_owner
    WITH CHECK (project_id IN (
        SELECT project_id FROM factory.project_identities
        WHERE role_name = session_user
    ));
CREATE POLICY task_plan_versions_isolated ON factory.task_plan_versions
    FOR SELECT TO PUBLIC
    USING (project_id IN (
        SELECT project_id FROM factory.project_identities
        WHERE role_name = session_user
    ));
CREATE POLICY task_plan_versions_insert ON factory.task_plan_versions
    FOR INSERT TO factory_executor_owner
    WITH CHECK (project_id IN (
        SELECT project_id FROM factory.project_identities
        WHERE role_name = session_user
    ));

GRANT SELECT ON factory.mission_versions, factory.task_plan_versions TO factory_runtime;
GRANT SELECT, INSERT ON factory.mission_versions, factory.task_plan_versions TO factory_executor_owner;

REVOKE ALL ON FUNCTION factory.record_mission_version(UUID, JSONB, TEXT) FROM PUBLIC;
REVOKE ALL ON FUNCTION factory.record_mission_version(UUID, JSONB, TEXT) FROM factory_runtime;
GRANT EXECUTE ON FUNCTION factory.record_mission_version(UUID, JSONB, TEXT) TO factory_runtime;
ALTER FUNCTION factory.record_mission_version(UUID, JSONB, TEXT) OWNER TO factory_executor_owner;

REVOKE ALL ON FUNCTION factory.record_task_plan_version(UUID, TEXT, INTEGER, JSONB, TEXT) FROM PUBLIC;
REVOKE ALL ON FUNCTION factory.record_task_plan_version(UUID, TEXT, INTEGER, JSONB, TEXT) FROM factory_runtime;
GRANT EXECUTE ON FUNCTION factory.record_task_plan_version(UUID, TEXT, INTEGER, JSONB, TEXT) TO factory_runtime;
ALTER FUNCTION factory.record_task_plan_version(UUID, TEXT, INTEGER, JSONB, TEXT) OWNER TO factory_executor_owner;

COMMIT;
