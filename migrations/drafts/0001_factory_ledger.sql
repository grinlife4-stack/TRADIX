-- DRAFT ONLY — NOT APPROVED FOR NEON EXECUTION.
-- CI may apply this file to a disposable PostgreSQL service for schema/constraint tests.
-- Never run against Production. Review ownership, grants, RLS, and migration strategy first.
BEGIN;

CREATE SCHEMA factory;

CREATE TABLE factory.projects (
    project_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_key TEXT NOT NULL UNIQUE
        CHECK (project_key ~ '^[a-z][a-z0-9-]{1,39}$'),
    display_name TEXT NOT NULL CHECK (length(trim(display_name)) BETWEEN 1 AND 120),
    repository_full_name TEXT NOT NULL
        CHECK (repository_full_name ~ '^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$'),
    status TEXT NOT NULL DEFAULT 'active'
        CHECK (status IN ('active', 'paused', 'archived')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE factory.tasks (
    task_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES factory.projects(project_id) ON DELETE RESTRICT,
    task_key TEXT NOT NULL,
    title TEXT NOT NULL CHECK (length(trim(title)) BETWEEN 1 AND 160),
    request_text TEXT NOT NULL CHECK (length(trim(request_text)) BETWEEN 1 AND 12000),
    acceptance_criteria JSONB NOT NULL
        CHECK (jsonb_typeof(acceptance_criteria) = 'array'
               AND jsonb_array_length(acceptance_criteria) BETWEEN 1 AND 30),
    risk_class TEXT NOT NULL CHECK (risk_class IN ('low', 'medium', 'high', 'critical')),
    approval_required BOOLEAN NOT NULL,
    status TEXT NOT NULL DEFAULT 'queued'
        CHECK (status IN (
            'queued', 'planned', 'implementing', 'testing', 'review',
            'candidate', 'deployed_test', 'verified', 'blocked', 'failed', 'cancelled'
        )),
    current_attempt INTEGER NOT NULL DEFAULT 0 CHECK (current_attempt >= 0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (project_id, task_key),
    CHECK (risk_class NOT IN ('high', 'critical') OR approval_required)
);

CREATE TABLE factory.task_attempts (
    attempt_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    task_id UUID NOT NULL REFERENCES factory.tasks(task_id) ON DELETE RESTRICT,
    attempt_number INTEGER NOT NULL CHECK (attempt_number > 0),
    worker_role TEXT NOT NULL CHECK (worker_role IN (
        'planner', 'implementer', 'tester', 'reviewer', 'release', 'observer'
    )),
    status TEXT NOT NULL DEFAULT 'queued'
        CHECK (status IN ('queued', 'running', 'succeeded', 'failed', 'cancelled')),
    branch_name TEXT,
    commit_sha TEXT CHECK (commit_sha IS NULL OR commit_sha ~ '^[0-9a-f]{40}$'),
    started_at TIMESTAMPTZ,
    finished_at TIMESTAMPTZ,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb
        CHECK (jsonb_typeof(metadata) = 'object'),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (task_id, attempt_number),
    UNIQUE (attempt_id, task_id)
);

CREATE TABLE factory.task_events (
    event_seq BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    event_id UUID NOT NULL DEFAULT gen_random_uuid() UNIQUE,
    task_id UUID NOT NULL REFERENCES factory.tasks(task_id) ON DELETE RESTRICT,
    attempt_id UUID,
    event_type TEXT NOT NULL CHECK (length(trim(event_type)) BETWEEN 1 AND 100),
    from_state TEXT CHECK (from_state IS NULL OR from_state IN (
        'queued', 'planned', 'implementing', 'testing', 'review',
        'candidate', 'deployed_test', 'verified', 'blocked', 'failed', 'cancelled'
    )),
    to_state TEXT CHECK (to_state IS NULL OR to_state IN (
        'queued', 'planned', 'implementing', 'testing', 'review',
        'candidate', 'deployed_test', 'verified', 'blocked', 'failed', 'cancelled'
    )),
    actor_type TEXT NOT NULL CHECK (actor_type IN ('human', 'system', 'agent', 'github')),
    actor_ref TEXT NOT NULL CHECK (length(trim(actor_ref)) BETWEEN 1 AND 200),
    idempotency_key TEXT NOT NULL UNIQUE CHECK (length(trim(idempotency_key)) BETWEEN 1 AND 255),
    payload JSONB NOT NULL DEFAULT '{}'::jsonb
        CHECK (jsonb_typeof(payload) = 'object'),
    occurred_at TIMESTAMPTZ,
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    FOREIGN KEY (attempt_id, task_id)
        REFERENCES factory.task_attempts(attempt_id, task_id) ON DELETE RESTRICT
);

CREATE INDEX task_events_task_seq_idx
    ON factory.task_events (task_id, event_seq);

CREATE TABLE factory.task_approvals (
    approval_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    task_id UUID NOT NULL REFERENCES factory.tasks(task_id) ON DELETE RESTRICT,
    attempt_id UUID,
    approval_round INTEGER NOT NULL CHECK (approval_round > 0),
    action TEXT NOT NULL CHECK (length(trim(action)) BETWEEN 1 AND 120),
    decision TEXT NOT NULL CHECK (decision IN ('approved', 'rejected')),
    decided_by TEXT NOT NULL CHECK (length(trim(decided_by)) BETWEEN 1 AND 200),
    rationale TEXT NOT NULL CHECK (length(trim(rationale)) BETWEEN 1 AND 4000),
    decision_scope JSONB NOT NULL DEFAULT '{}'::jsonb
        CHECK (jsonb_typeof(decision_scope) = 'object'),
    decided_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (task_id, action, approval_round),
    FOREIGN KEY (attempt_id, task_id)
        REFERENCES factory.task_attempts(attempt_id, task_id) ON DELETE RESTRICT
);

CREATE TABLE factory.task_artifacts (
    artifact_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    task_id UUID NOT NULL REFERENCES factory.tasks(task_id) ON DELETE RESTRICT,
    attempt_id UUID,
    artifact_type TEXT NOT NULL CHECK (length(trim(artifact_type)) BETWEEN 1 AND 80),
    object_uri TEXT NOT NULL CHECK (length(trim(object_uri)) BETWEEN 1 AND 2048),
    sha256 TEXT NOT NULL CHECK (sha256 ~ '^[0-9a-f]{64}$'),
    byte_size BIGINT NOT NULL CHECK (byte_size >= 0),
    content_type TEXT NOT NULL DEFAULT 'application/octet-stream',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (task_id, object_uri, sha256),
    UNIQUE (artifact_id, task_id),
    UNIQUE (artifact_id, task_id, attempt_id),
    FOREIGN KEY (attempt_id, task_id)
        REFERENCES factory.task_attempts(attempt_id, task_id) ON DELETE RESTRICT
);

CREATE TABLE factory.task_evidence (
    evidence_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    task_id UUID NOT NULL REFERENCES factory.tasks(task_id) ON DELETE RESTRICT,
    attempt_id UUID NOT NULL,
    artifact_id UUID NOT NULL,
    evidence_type TEXT NOT NULL CHECK (length(trim(evidence_type)) BETWEEN 1 AND 100),
    description TEXT NOT NULL DEFAULT '',
    recorded_by TEXT NOT NULL CHECK (length(trim(recorded_by)) BETWEEN 1 AND 200),
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb
        CHECK (jsonb_typeof(metadata) = 'object'),
    FOREIGN KEY (attempt_id, task_id)
        REFERENCES factory.task_attempts(attempt_id, task_id) ON DELETE RESTRICT,
    FOREIGN KEY (artifact_id, task_id, attempt_id)
        REFERENCES factory.task_artifacts(artifact_id, task_id, attempt_id) ON DELETE RESTRICT
);

CREATE FUNCTION factory.reject_immutable_row_mutation()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE EXCEPTION 'Rows in %.% are append-only', TG_TABLE_SCHEMA, TG_TABLE_NAME;
END;
$$;

CREATE TRIGGER task_events_append_only
    BEFORE UPDATE OR DELETE ON factory.task_events
    FOR EACH ROW EXECUTE FUNCTION factory.reject_immutable_row_mutation();
CREATE TRIGGER task_events_no_truncate
    BEFORE TRUNCATE ON factory.task_events
    FOR EACH STATEMENT EXECUTE FUNCTION factory.reject_immutable_row_mutation();

CREATE TRIGGER task_approvals_append_only
    BEFORE UPDATE OR DELETE ON factory.task_approvals
    FOR EACH ROW EXECUTE FUNCTION factory.reject_immutable_row_mutation();
CREATE TRIGGER task_approvals_no_truncate
    BEFORE TRUNCATE ON factory.task_approvals
    FOR EACH STATEMENT EXECUTE FUNCTION factory.reject_immutable_row_mutation();

CREATE TRIGGER task_evidence_append_only
    BEFORE UPDATE OR DELETE ON factory.task_evidence
    FOR EACH ROW EXECUTE FUNCTION factory.reject_immutable_row_mutation();
CREATE TRIGGER task_evidence_no_truncate
    BEFORE TRUNCATE ON factory.task_evidence
    FOR EACH STATEMENT EXECUTE FUNCTION factory.reject_immutable_row_mutation();

CREATE TRIGGER task_artifacts_append_only
    BEFORE UPDATE OR DELETE ON factory.task_artifacts
    FOR EACH ROW EXECUTE FUNCTION factory.reject_immutable_row_mutation();
CREATE TRIGGER task_artifacts_no_truncate
    BEFORE TRUNCATE ON factory.task_artifacts
    FOR EACH STATEMENT EXECUTE FUNCTION factory.reject_immutable_row_mutation();

REVOKE UPDATE, DELETE, TRUNCATE ON factory.task_events FROM PUBLIC;
REVOKE UPDATE, DELETE, TRUNCATE ON factory.task_approvals FROM PUBLIC;
REVOKE UPDATE, DELETE, TRUNCATE ON factory.task_evidence FROM PUBLIC;
REVOKE UPDATE, DELETE, TRUNCATE ON factory.task_artifacts FROM PUBLIC;


-- The only supported lifecycle write path: lock the task, validate the edge,
-- enforce evidence/approval gates, append the event, and update the projection
-- in one PostgreSQL transaction. Callers must not update tasks.status directly.
CREATE FUNCTION factory.transition_task(
    p_task_id UUID,
    p_to_state TEXT,
    p_event_type TEXT,
    p_actor_type TEXT,
    p_actor_ref TEXT,
    p_idempotency_key TEXT,
    p_attempt_id UUID DEFAULT NULL,
    p_payload JSONB DEFAULT '{}'::jsonb
)
RETURNS BIGINT
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, factory, pg_temp
AS $body$
DECLARE
    v_task factory.tasks%ROWTYPE;
    v_existing factory.task_events%ROWTYPE;
    v_event_seq BIGINT;
    v_required_evidence TEXT;
    v_allowed BOOLEAN := FALSE;
BEGIN
    IF p_task_id IS NULL
       OR p_to_state IS NULL
       OR p_event_type IS NULL OR length(trim(p_event_type)) NOT BETWEEN 1 AND 100
       OR p_actor_type IS NULL OR p_actor_type NOT IN ('system', 'agent', 'github')
       OR p_actor_ref IS NULL OR length(trim(p_actor_ref)) NOT BETWEEN 1 AND 200
       OR p_idempotency_key IS NULL OR length(trim(p_idempotency_key)) NOT BETWEEN 1 AND 255
       OR p_payload IS NULL OR jsonb_typeof(p_payload) <> 'object' THEN
        RAISE EXCEPTION 'invalid task transition arguments';
    END IF;

    SELECT * INTO v_task
    FROM factory.tasks
    WHERE task_id = p_task_id
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'task not found: %', p_task_id;
    END IF;

    -- Exact retries are harmless; reusing a key for different intent is not.
    SELECT * INTO v_existing
    FROM factory.task_events
    WHERE idempotency_key = p_idempotency_key;

    IF FOUND THEN
        IF v_existing.task_id = p_task_id
           AND v_existing.to_state = p_to_state
           AND v_existing.event_type = p_event_type
           AND v_existing.attempt_id IS NOT DISTINCT FROM p_attempt_id
           AND v_existing.actor_type = p_actor_type
           AND v_existing.actor_ref = p_actor_ref
           AND v_existing.payload = p_payload THEN
            RETURN v_existing.event_seq;
        END IF;
        RAISE EXCEPTION 'idempotency key reused with different transition intent';
    END IF;

    v_allowed :=
        (v_task.status = 'queued' AND p_to_state IN ('planned','blocked','failed','cancelled'))
        OR (v_task.status = 'planned' AND p_to_state IN ('implementing','blocked','failed','cancelled'))
        OR (v_task.status = 'implementing' AND p_to_state IN ('testing','blocked','failed','cancelled'))
        OR (v_task.status = 'testing' AND p_to_state IN ('review','implementing','blocked','failed','cancelled'))
        OR (v_task.status = 'review' AND p_to_state IN ('candidate','implementing','blocked','failed','cancelled'))
        OR (v_task.status = 'candidate' AND p_to_state IN ('deployed_test','blocked','failed','cancelled'))
        OR (v_task.status = 'deployed_test' AND p_to_state IN ('verified','blocked','failed','cancelled'))
        OR (v_task.status = 'blocked' AND p_to_state IN ('planned','cancelled'));

    IF NOT v_allowed THEN
        RAISE EXCEPTION 'task transition not allowed: % -> %', v_task.status, p_to_state;
    END IF;

    IF v_task.status = 'planned' AND p_to_state = 'implementing'
       AND v_task.approval_required
       AND NOT EXISTS (
           SELECT 1 FROM factory.task_approvals
           WHERE task_id = p_task_id
             AND action = 'begin_implementation'
             AND decision = 'approved'
       ) THEN
        RAISE EXCEPTION 'human approval required before implementation';
    END IF;

    v_required_evidence := CASE
        WHEN v_task.status = 'testing' AND p_to_state = 'review' THEN 'test_report'
        WHEN v_task.status = 'review' AND p_to_state = 'candidate' THEN 'review_report'
        WHEN v_task.status = 'deployed_test' AND p_to_state = 'verified' THEN 'health_check'
        ELSE NULL
    END;

    IF v_required_evidence IS NOT NULL AND NOT EXISTS (
        SELECT 1
        FROM factory.task_evidence e
        WHERE e.task_id = p_task_id
          AND e.evidence_type = v_required_evidence
          AND (p_attempt_id IS NULL OR e.attempt_id = p_attempt_id)
    ) THEN
        RAISE EXCEPTION 'required evidence missing: %', v_required_evidence;
    END IF;

    INSERT INTO factory.task_events (
        task_id, attempt_id, event_type, from_state, to_state,
        actor_type, actor_ref, idempotency_key, payload
    ) VALUES (
        p_task_id, p_attempt_id, p_event_type, v_task.status, p_to_state,
        p_actor_type, p_actor_ref, p_idempotency_key, p_payload
    ) RETURNING event_seq INTO v_event_seq;

    UPDATE factory.tasks
    SET status = p_to_state, updated_at = now()
    WHERE task_id = p_task_id;

    RETURN v_event_seq;
END;
$body$;

-- Runtime access is deliberately read-only except for the SECURITY DEFINER
-- transition function. Provisioning this NOLOGIN role is part of this draft
-- migration and must be reviewed before any managed-database application.
DO $roles$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'factory_executor_owner') THEN
        EXECUTE 'CREATE ROLE factory_executor_owner NOLOGIN NOINHERIT';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'factory_runtime') THEN
        EXECUTE 'CREATE ROLE factory_runtime NOLOGIN NOINHERIT';
    END IF;
END
$roles$;

-- PostgreSQL 16+ does not grant SET ROLE to a non-superuser that creates
-- another role with CREATEROLE; its automatic creator membership has SET FALSE.
-- ALTER FUNCTION ... OWNER TO requires the migration role to SET ROLE to the
-- target owner, so grant that narrowly to the current migration identity.
GRANT factory_executor_owner TO CURRENT_USER WITH SET TRUE, INHERIT FALSE;

REVOKE ALL ON SCHEMA factory FROM PUBLIC;
REVOKE CREATE ON SCHEMA factory FROM PUBLIC;
GRANT USAGE ON SCHEMA factory TO factory_runtime;

REVOKE ALL ON ALL TABLES IN SCHEMA factory FROM PUBLIC;
REVOKE ALL ON ALL SEQUENCES IN SCHEMA factory FROM PUBLIC;
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA factory FROM PUBLIC;

GRANT SELECT ON ALL TABLES IN SCHEMA factory TO factory_runtime;
REVOKE INSERT, UPDATE, DELETE, TRUNCATE, REFERENCES, TRIGGER
    ON ALL TABLES IN SCHEMA factory FROM factory_runtime;
REVOKE ALL ON ALL SEQUENCES IN SCHEMA factory FROM factory_runtime;

-- Give the SECURITY DEFINER function a dedicated, non-login owner with
-- only the table privileges its body requires. It is not a superuser or table owner.
GRANT USAGE, CREATE ON SCHEMA factory TO factory_executor_owner;
GRANT SELECT, UPDATE ON factory.tasks TO factory_executor_owner;
GRANT SELECT, INSERT ON factory.task_events TO factory_executor_owner;
GRANT SELECT ON factory.task_approvals, factory.task_evidence TO factory_executor_owner;

-- Revoke/grant function ACLs while the migration identity still owns it.
-- After ownership transfer, a non-superuser migration identity no longer
-- owns the function and cannot alter its ACL without an explicit grant option.
REVOKE ALL ON FUNCTION factory.transition_task(
    UUID, TEXT, TEXT, TEXT, TEXT, TEXT, UUID, JSONB
) FROM PUBLIC;
REVOKE ALL ON FUNCTION factory.transition_task(
    UUID, TEXT, TEXT, TEXT, TEXT, TEXT, UUID, JSONB
) FROM factory_runtime;
GRANT EXECUTE ON FUNCTION factory.transition_task(
    UUID, TEXT, TEXT, TEXT, TEXT, TEXT, UUID, JSONB
) TO factory_runtime;

ALTER FUNCTION factory.transition_task(
    UUID, TEXT, TEXT, TEXT, TEXT, TEXT, UUID, JSONB
) OWNER TO factory_executor_owner;
REVOKE CREATE ON SCHEMA factory FROM factory_executor_owner;

-- Future objects created by the migration owner inherit the same safe defaults.
ALTER DEFAULT PRIVILEGES FOR ROLE CURRENT_USER IN SCHEMA factory
    REVOKE ALL ON TABLES FROM PUBLIC;
ALTER DEFAULT PRIVILEGES FOR ROLE CURRENT_USER IN SCHEMA factory
    GRANT SELECT ON TABLES TO factory_runtime;
ALTER DEFAULT PRIVILEGES FOR ROLE CURRENT_USER IN SCHEMA factory
    REVOKE EXECUTE ON FUNCTIONS FROM PUBLIC;

COMMIT;
