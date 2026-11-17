BEGIN;

-- Block new task/attempt writes from racing the preflight and migration.
-- Lock order matches worker acquisition: task first, then attempt.
LOCK TABLE factory.tasks IN SHARE ROW EXCLUSIVE MODE;
LOCK TABLE factory.task_attempts IN SHARE ROW EXCLUSIVE MODE;

-- Migration owner temporarily bypasses forced RLS only inside this transaction
-- so the preflight sees every project's legacy work. Restore FORCE before commit.
ALTER TABLE factory.tasks NO FORCE ROW LEVEL SECURITY;
ALTER TABLE factory.task_attempts NO FORCE ROW LEVEL SECURITY;

DO $lease_rollout_preflight$
BEGIN
    IF EXISTS (
        SELECT 1 FROM factory.task_attempts WHERE status = 'running'
    ) OR EXISTS (
        SELECT 1 FROM factory.tasks
        WHERE status IN ('planned', 'implementing', 'testing', 'review', 'candidate', 'deployed_test')
    ) THEN
        RAISE EXCEPTION
            'worker lease migration refused: drain or explicitly reconcile active tasks and running attempts first';
    END IF;
END;
$lease_rollout_preflight$;

ALTER TABLE factory.tasks FORCE ROW LEVEL SECURITY;
ALTER TABLE factory.task_attempts FORCE ROW LEVEL SECURITY;

-- Worker leases and monotonic fencing tokens.
-- This migration is forward-only. It does not grant any runtime direct table access.
CREATE TABLE factory.task_lease_counters (
    task_id UUID PRIMARY KEY REFERENCES factory.tasks(task_id) ON DELETE RESTRICT,
    last_token BIGINT NOT NULL DEFAULT 0 CHECK (last_token >= 0)
);

CREATE TABLE factory.task_leases (
    task_id UUID PRIMARY KEY REFERENCES factory.tasks(task_id) ON DELETE RESTRICT,
    attempt_id UUID NOT NULL,
    worker_id TEXT NOT NULL CHECK (length(trim(worker_id)) BETWEEN 1 AND 255),
    fencing_token BIGINT NOT NULL CHECK (fencing_token > 0),
    expires_at TIMESTAMPTZ NOT NULL,
    acquired_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    renewed_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    FOREIGN KEY (attempt_id, task_id)
        REFERENCES factory.task_attempts(attempt_id, task_id) ON DELETE RESTRICT
);

REVOKE ALL ON factory.task_lease_counters, factory.task_leases FROM PUBLIC, factory_runtime;
GRANT SELECT, INSERT, UPDATE ON factory.task_lease_counters, factory.task_leases TO factory_executor_owner;
GRANT DELETE ON factory.task_leases TO factory_executor_owner;

ALTER TABLE factory.task_lease_counters ENABLE ROW LEVEL SECURITY;
ALTER TABLE factory.task_lease_counters FORCE ROW LEVEL SECURITY;
ALTER TABLE factory.task_leases ENABLE ROW LEVEL SECURITY;
ALTER TABLE factory.task_leases FORCE ROW LEVEL SECURITY;

CREATE POLICY lease_counters_executor_owner ON factory.task_lease_counters
    FOR ALL TO factory_executor_owner USING (true) WITH CHECK (true);
CREATE POLICY leases_executor_owner ON factory.task_leases
    FOR ALL TO factory_executor_owner USING (true) WITH CHECK (true);

-- Attempt creation is separate from ownership acquisition. Existing callers
-- continue to create idempotent attempts, but new attempts start queued.
CREATE FUNCTION factory.queue_new_task_attempt()
RETURNS TRIGGER
LANGUAGE plpgsql
SET search_path = pg_catalog, factory, pg_temp
AS $queue_attempt$
BEGIN
    NEW.status := 'queued';
    NEW.started_at := NULL;
    NEW.finished_at := NULL;
    RETURN NEW;
END;
$queue_attempt$;

CREATE TRIGGER task_attempts_start_queued
    BEFORE INSERT ON factory.task_attempts
    FOR EACH ROW EXECUTE FUNCTION factory.queue_new_task_attempt();

CREATE FUNCTION factory.acquire_task_lease(
    p_task_id UUID,
    p_attempt_id UUID,
    p_worker_id TEXT,
    p_ttl_seconds INTEGER DEFAULT 60
)
RETURNS TABLE(fencing_token BIGINT, expires_at TIMESTAMPTZ)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, factory, pg_temp
AS $acquire_lease$
DECLARE
    v_project_id UUID;
    v_task factory.tasks%ROWTYPE;
    v_attempt factory.task_attempts%ROWTYPE;
    v_lease factory.task_leases%ROWTYPE;
    v_token BIGINT;
BEGIN
    IF p_task_id IS NULL OR p_attempt_id IS NULL
       OR p_worker_id IS NULL OR length(trim(p_worker_id)) NOT BETWEEN 1 AND 255
       OR p_ttl_seconds NOT BETWEEN 5 AND 300 THEN
        RAISE EXCEPTION 'invalid task lease arguments';
    END IF;

    IF NOT pg_catalog.pg_has_role(session_user, 'factory_runtime', 'MEMBER')
       OR pg_catalog.pg_has_role(session_user, 'factory_approval_authority', 'MEMBER')
       OR pg_catalog.pg_has_role(session_user, 'factory_executor_owner', 'MEMBER') THEN
        RAISE EXCEPTION 'session identity is not an isolated product runtime';
    END IF;

    SELECT project_id INTO v_project_id
    FROM factory.project_identities
    WHERE role_name = session_user AND identity_kind = 'runtime';
    IF NOT FOUND THEN
        RAISE EXCEPTION 'runtime identity has no product mapping';
    END IF;

    SELECT * INTO v_task
    FROM factory.tasks
    WHERE task_id = p_task_id AND project_id = v_project_id
    FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'task not found for this product runtime';
    END IF;

    SELECT * INTO v_attempt
    FROM factory.task_attempts
    WHERE task_id = p_task_id AND attempt_id = p_attempt_id
    FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'attempt not found for this product runtime';
    END IF;
    IF v_attempt.status NOT IN ('queued','running') THEN
        RAISE EXCEPTION 'only queued or running attempts can acquire a lease';
    END IF;
    IF v_task.approval_required AND NOT EXISTS (
        SELECT 1
        FROM factory.task_approvals ap
        WHERE ap.task_id = p_task_id
          AND ap.attempt_id = p_attempt_id
          AND ap.action = 'begin_implementation'
          AND ap.decision = 'approved'
          AND ap.decision_scope = v_task.approval_scope
    ) THEN
        RAISE EXCEPTION 'human approval required for this attempt and decision scope';
    END IF;

    SELECT * INTO v_lease
    FROM factory.task_leases
    WHERE task_id = p_task_id
    FOR UPDATE;

    IF FOUND AND v_lease.expires_at > clock_timestamp() THEN
        IF v_lease.attempt_id = p_attempt_id AND v_lease.worker_id = p_worker_id THEN
            RETURN QUERY SELECT v_lease.fencing_token, v_lease.expires_at;
            RETURN;
        END IF;
        RAISE EXCEPTION 'task already has a live lease';
    END IF;

    IF FOUND AND v_lease.attempt_id <> p_attempt_id THEN
        RAISE EXCEPTION 'expired lease belongs to another attempt; explicit attempt recovery required';
    END IF;

    INSERT INTO factory.task_lease_counters(task_id, last_token)
    VALUES (p_task_id, 1)
    ON CONFLICT (task_id)
    DO UPDATE SET last_token = factory.task_lease_counters.last_token + 1
    RETURNING last_token INTO v_token;

    INSERT INTO factory.task_leases(
        task_id, attempt_id, worker_id, fencing_token, expires_at, acquired_at, renewed_at
    ) VALUES (
        p_task_id, p_attempt_id, p_worker_id, v_token,
        clock_timestamp() + make_interval(secs => p_ttl_seconds),
        clock_timestamp(), clock_timestamp()
    )
    ON CONFLICT (task_id) DO UPDATE SET
        attempt_id = EXCLUDED.attempt_id,
        worker_id = EXCLUDED.worker_id,
        fencing_token = EXCLUDED.fencing_token,
        expires_at = EXCLUDED.expires_at,
        acquired_at = EXCLUDED.acquired_at,
        renewed_at = EXCLUDED.renewed_at
    RETURNING * INTO v_lease;

    UPDATE factory.task_attempts
    SET status = 'running',
        started_at = COALESCE(started_at, clock_timestamp()),
        finished_at = NULL
    WHERE task_id = p_task_id AND attempt_id = p_attempt_id;

    RETURN QUERY SELECT v_lease.fencing_token, v_lease.expires_at;
END;
$acquire_lease$;

CREATE FUNCTION factory.renew_task_lease(
    p_task_id UUID,
    p_attempt_id UUID,
    p_worker_id TEXT,
    p_fencing_token BIGINT,
    p_ttl_seconds INTEGER DEFAULT 60
)
RETURNS TIMESTAMPTZ
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, factory, pg_temp
AS $renew_lease$
DECLARE
    v_expires_at TIMESTAMPTZ;
BEGIN
    IF p_ttl_seconds NOT BETWEEN 5 AND 300 THEN
        RAISE EXCEPTION 'invalid lease TTL';
    END IF;
    IF NOT pg_catalog.pg_has_role(session_user, 'factory_runtime', 'MEMBER')
       OR pg_catalog.pg_has_role(session_user, 'factory_approval_authority', 'MEMBER')
       OR pg_catalog.pg_has_role(session_user, 'factory_executor_owner', 'MEMBER') THEN
        RAISE EXCEPTION 'session identity is not an isolated product runtime';
    END IF;

    UPDATE factory.task_leases
    SET expires_at = clock_timestamp() + make_interval(secs => p_ttl_seconds),
        renewed_at = clock_timestamp()
    WHERE task_id = p_task_id
      AND attempt_id = p_attempt_id
      AND worker_id = p_worker_id
      AND fencing_token = p_fencing_token
      AND expires_at > clock_timestamp()
      AND EXISTS (
          SELECT 1
          FROM factory.tasks t
          JOIN factory.task_attempts a
            ON a.task_id = t.task_id
           AND a.attempt_id = p_attempt_id
           AND a.status = 'running'
          JOIN factory.project_identities i
            ON i.project_id = t.project_id
           AND i.role_name = session_user
           AND i.identity_kind = 'runtime'
          WHERE t.task_id = p_task_id
      )
    RETURNING expires_at INTO v_expires_at;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'lease is missing, expired, or owned by another worker';
    END IF;
    RETURN v_expires_at;
END;
$renew_lease$;

CREATE FUNCTION factory.assert_task_lease(
    p_task_id UUID,
    p_attempt_id UUID,
    p_worker_id TEXT,
    p_fencing_token BIGINT
)
RETURNS VOID
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, factory, pg_temp
AS $assert_lease$
DECLARE
    v_project_id UUID;
BEGIN
    IF NOT pg_catalog.pg_has_role(session_user, 'factory_runtime', 'MEMBER')
       OR pg_catalog.pg_has_role(session_user, 'factory_approval_authority', 'MEMBER')
       OR pg_catalog.pg_has_role(session_user, 'factory_executor_owner', 'MEMBER') THEN
        RAISE EXCEPTION 'session identity is not an isolated product runtime';
    END IF;

    -- Lock order is task first, then lease. acquire_task_lease uses the same
    -- order. Holding the task lock through the wrapper's transaction prevents
    -- a takeover between lease validation and the delegated write.
    SELECT t.project_id INTO v_project_id
    FROM factory.tasks t
    JOIN factory.project_identities i
      ON i.project_id = t.project_id
     AND i.role_name = session_user
     AND i.identity_kind = 'runtime'
    WHERE t.task_id = p_task_id
    FOR UPDATE OF t;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'valid task lease and fencing token required';
    END IF;

    PERFORM 1
    FROM factory.task_leases l
    JOIN factory.task_attempts a
      ON a.task_id = l.task_id AND a.attempt_id = l.attempt_id
    WHERE l.task_id = p_task_id
      AND l.attempt_id = p_attempt_id
      AND l.worker_id = p_worker_id
      AND l.fencing_token = p_fencing_token
      AND l.expires_at > clock_timestamp()
      AND a.attempt_id = p_attempt_id
      AND a.task_id = p_task_id
    FOR UPDATE OF l;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'valid task lease and fencing token required';
    END IF;
END;
$assert_lease$;

CREATE FUNCTION factory.transition_task_fenced(
    p_task_id UUID,
    p_fencing_token BIGINT,
    p_worker_id TEXT,
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
AS $transition_fenced$
DECLARE
    v_attempt_status TEXT;
BEGIN
    PERFORM factory.assert_task_lease(
        p_task_id, p_attempt_id, p_worker_id, p_fencing_token
    );
    SELECT status INTO v_attempt_status
    FROM factory.task_attempts
    WHERE task_id = p_task_id AND attempt_id = p_attempt_id;

    IF v_attempt_status = 'running' THEN
        NULL;
    ELSIF (v_attempt_status = 'succeeded' AND p_to_state = 'verified')
       OR (v_attempt_status = 'failed' AND p_to_state = 'failed')
       OR (v_attempt_status = 'cancelled' AND p_to_state = 'cancelled') THEN
        NULL;
    ELSE
        RAISE EXCEPTION 'task transition is not permitted for attempt status %', v_attempt_status;
    END IF;

    RETURN factory.transition_task(
        p_task_id, p_to_state, p_event_type, p_actor_type, p_actor_ref,
        p_idempotency_key, p_attempt_id, p_payload
    );
END;
$transition_fenced$;

CREATE FUNCTION factory.record_task_evidence_fenced(
    p_task_id UUID,
    p_attempt_id UUID,
    p_worker_id TEXT,
    p_fencing_token BIGINT,
    p_artifact_type TEXT,
    p_object_uri TEXT,
    p_sha256 TEXT,
    p_byte_size BIGINT,
    p_content_type TEXT,
    p_evidence_type TEXT,
    p_description TEXT DEFAULT '',
    p_metadata JSONB DEFAULT '{}'::jsonb
)
RETURNS UUID
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, factory, pg_temp
AS $evidence_fenced$
DECLARE
    v_attempt_status TEXT;
BEGIN
    PERFORM factory.assert_task_lease(
        p_task_id, p_attempt_id, p_worker_id, p_fencing_token
    );
    SELECT status INTO v_attempt_status
    FROM factory.task_attempts
    WHERE task_id = p_task_id AND attempt_id = p_attempt_id
    FOR UPDATE;

    IF v_attempt_status IS DISTINCT FROM 'running' THEN
        RAISE EXCEPTION 'evidence can only be recorded for a running attempt';
    END IF;

    RETURN factory.record_task_evidence(
        p_task_id, p_attempt_id, p_artifact_type, p_object_uri, p_sha256,
        p_byte_size, p_content_type, p_evidence_type, p_description, p_metadata
    );
END;
$evidence_fenced$;

CREATE FUNCTION factory.finish_task_attempt_fenced(
    p_task_id UUID,
    p_attempt_id UUID,
    p_worker_id TEXT,
    p_fencing_token BIGINT,
    p_outcome TEXT
)
RETURNS TEXT
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, factory, pg_temp
AS $finish_fenced$
BEGIN
    PERFORM factory.assert_task_lease(
        p_task_id, p_attempt_id, p_worker_id, p_fencing_token
    );
    RETURN factory.finish_task_attempt(p_task_id, p_attempt_id, p_outcome);
END;
$finish_fenced$;

CREATE FUNCTION factory.release_task_lease(
    p_task_id UUID,
    p_attempt_id UUID,
    p_worker_id TEXT,
    p_fencing_token BIGINT
)
RETURNS BOOLEAN
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, factory, pg_temp
AS $release_lease$
BEGIN
    PERFORM factory.assert_task_lease(
        p_task_id, p_attempt_id, p_worker_id, p_fencing_token
    );
    IF EXISTS (
        SELECT 1 FROM factory.task_attempts
        WHERE task_id = p_task_id AND attempt_id = p_attempt_id AND status = 'running'
    ) THEN
        RAISE EXCEPTION 'cannot release a lease while its attempt is running';
    END IF;
    DELETE FROM factory.task_leases
    WHERE task_id = p_task_id AND attempt_id = p_attempt_id
      AND worker_id = p_worker_id AND fencing_token = p_fencing_token;
    RETURN FOUND;
END;
$release_lease$;

-- The legacy APIs are already owned by factory_executor_owner from 0001.
-- Switch to that owner explicitly before changing their ACLs; the migration
-- login has SET-only membership and must not inherit those privileges.
GRANT CREATE ON SCHEMA factory TO factory_executor_owner;
SET ROLE factory_executor_owner;
REVOKE ALL ON FUNCTION factory.transition_task(UUID, TEXT, TEXT, TEXT, TEXT, TEXT, UUID, JSONB)
    FROM PUBLIC, factory_runtime;
REVOKE ALL ON FUNCTION factory.record_task_evidence(UUID, UUID, TEXT, TEXT, TEXT, BIGINT, TEXT, TEXT, TEXT, JSONB)
    FROM PUBLIC, factory_runtime;
REVOKE ALL ON FUNCTION factory.finish_task_attempt(UUID, UUID, TEXT)
    FROM PUBLIC, factory_runtime;
RESET ROLE;

-- PostgreSQL grants EXECUTE to PUBLIC on new functions by default.
-- Remove that default from every API and grant only the product runtime role.
REVOKE ALL ON FUNCTION factory.acquire_task_lease(UUID, UUID, TEXT, INTEGER) FROM PUBLIC;
REVOKE ALL ON FUNCTION factory.renew_task_lease(UUID, UUID, TEXT, BIGINT, INTEGER) FROM PUBLIC;
REVOKE ALL ON FUNCTION factory.assert_task_lease(UUID, UUID, TEXT, BIGINT) FROM PUBLIC, factory_runtime;
REVOKE ALL ON FUNCTION factory.transition_task_fenced(UUID, BIGINT, TEXT, TEXT, TEXT, TEXT, TEXT, TEXT, UUID, JSONB) FROM PUBLIC;
REVOKE ALL ON FUNCTION factory.record_task_evidence_fenced(UUID, UUID, TEXT, BIGINT, TEXT, TEXT, TEXT, BIGINT, TEXT, TEXT, TEXT, JSONB) FROM PUBLIC;
REVOKE ALL ON FUNCTION factory.finish_task_attempt_fenced(UUID, UUID, TEXT, BIGINT, TEXT) FROM PUBLIC;
REVOKE ALL ON FUNCTION factory.release_task_lease(UUID, UUID, TEXT, BIGINT) FROM PUBLIC;

GRANT EXECUTE ON FUNCTION factory.acquire_task_lease(UUID, UUID, TEXT, INTEGER) TO factory_runtime;
GRANT EXECUTE ON FUNCTION factory.renew_task_lease(UUID, UUID, TEXT, BIGINT, INTEGER) TO factory_runtime;
GRANT EXECUTE ON FUNCTION factory.transition_task_fenced(UUID, BIGINT, TEXT, TEXT, TEXT, TEXT, TEXT, TEXT, UUID, JSONB) TO factory_runtime;
GRANT EXECUTE ON FUNCTION factory.record_task_evidence_fenced(UUID, UUID, TEXT, BIGINT, TEXT, TEXT, TEXT, BIGINT, TEXT, TEXT, TEXT, JSONB) TO factory_runtime;
GRANT EXECUTE ON FUNCTION factory.finish_task_attempt_fenced(UUID, UUID, TEXT, BIGINT, TEXT) TO factory_runtime;
GRANT EXECUTE ON FUNCTION factory.release_task_lease(UUID, UUID, TEXT, BIGINT) TO factory_runtime;
ALTER FUNCTION factory.acquire_task_lease(UUID, UUID, TEXT, INTEGER) OWNER TO factory_executor_owner;
ALTER FUNCTION factory.renew_task_lease(UUID, UUID, TEXT, BIGINT, INTEGER) OWNER TO factory_executor_owner;
ALTER FUNCTION factory.assert_task_lease(UUID, UUID, TEXT, BIGINT) OWNER TO factory_executor_owner;
ALTER FUNCTION factory.transition_task_fenced(UUID, BIGINT, TEXT, TEXT, TEXT, TEXT, TEXT, TEXT, UUID, JSONB) OWNER TO factory_executor_owner;
ALTER FUNCTION factory.record_task_evidence_fenced(UUID, UUID, TEXT, BIGINT, TEXT, TEXT, TEXT, BIGINT, TEXT, TEXT, TEXT, JSONB) OWNER TO factory_executor_owner;
ALTER FUNCTION factory.finish_task_attempt_fenced(UUID, UUID, TEXT, BIGINT, TEXT) OWNER TO factory_executor_owner;
ALTER FUNCTION factory.release_task_lease(UUID, UUID, TEXT, BIGINT) OWNER TO factory_executor_owner;

REVOKE ALL ON FUNCTION factory.queue_new_task_attempt() FROM PUBLIC;
REVOKE CREATE ON SCHEMA factory FROM factory_executor_owner;

COMMIT;
