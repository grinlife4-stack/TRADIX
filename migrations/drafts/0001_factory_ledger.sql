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
    product_type TEXT NOT NULL DEFAULT 'unspecified'
        CHECK (length(trim(product_type)) BETWEEN 1 AND 80),
    -- A product may be physical, service-based, hybrid, or otherwise non-software.
    -- Repository metadata is optional and applies only when the product uses Git.
    repository_full_name TEXT
        CHECK (
            repository_full_name IS NULL OR
            repository_full_name ~ '^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$'
        ),
    status TEXT NOT NULL DEFAULT 'active'
        CHECK (status IN ('active', 'paused', 'archived')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()

);

-- Maps each database login identity to exactly one project. session_user is
-- used so SET ROLE cannot change the project identity.

-- Product dossiers are immutable, versioned snapshots scoped to one product.
CREATE TABLE factory.product_dossier_versions (
    dossier_version_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES factory.projects(project_id) ON DELETE RESTRICT,
    version_no INTEGER NOT NULL CHECK (version_no > 0),
    idempotency_key TEXT NOT NULL CHECK (length(trim(idempotency_key)) BETWEEN 1 AND 255),
    dossier JSONB NOT NULL CHECK (jsonb_typeof(dossier) = 'object'),
    created_by_login NAME NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (project_id, version_no),
    UNIQUE (project_id, idempotency_key)
);

CREATE INDEX product_dossier_versions_latest_idx
    ON factory.product_dossier_versions (project_id, version_no DESC);

REVOKE UPDATE, DELETE, TRUNCATE ON factory.product_dossier_versions FROM PUBLIC;

CREATE TABLE factory.project_identities (
    role_name NAME PRIMARY KEY,
    project_id UUID NOT NULL REFERENCES factory.projects(project_id) ON DELETE RESTRICT,
    identity_kind TEXT NOT NULL CHECK (identity_kind IN ('runtime', 'approval')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (project_id, identity_kind)
);

CREATE FUNCTION factory.validate_project_identity()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path = pg_catalog, factory, pg_temp
AS $identity$
DECLARE
    v_role pg_catalog.pg_roles%ROWTYPE;
    v_runtime BOOLEAN;
    v_approver BOOLEAN;
BEGIN
    SELECT * INTO v_role FROM pg_catalog.pg_roles WHERE rolname = NEW.role_name;
    IF NOT FOUND OR NOT v_role.rolcanlogin OR NOT v_role.rolinherit OR v_role.rolsuper OR v_role.rolcreatedb
       OR v_role.rolcreaterole OR v_role.rolbypassrls THEN
        RAISE EXCEPTION 'project identity must be an existing restricted LOGIN role';
    END IF;

    v_runtime := pg_catalog.pg_has_role(NEW.role_name, 'factory_runtime', 'MEMBER');
    v_approver := pg_catalog.pg_has_role(NEW.role_name, 'factory_approval_authority', 'MEMBER');
    IF v_runtime = v_approver THEN
        RAISE EXCEPTION 'project identity must belong to exactly one of runtime or approval authority';
    END IF;
    IF (v_runtime AND NEW.identity_kind <> 'runtime')
       OR (v_approver AND NEW.identity_kind <> 'approval') THEN
        RAISE EXCEPTION 'project identity kind does not match its authority role';
    END IF;
    IF pg_catalog.pg_has_role(NEW.role_name, 'factory_executor_owner', 'MEMBER') THEN
        RAISE EXCEPTION 'project identity cannot belong to factory_executor_owner';
    END IF;
    IF EXISTS (
        SELECT 1
        FROM pg_catalog.pg_auth_members m
        JOIN pg_catalog.pg_roles granted_role ON granted_role.oid = m.roleid
        WHERE pg_catalog.pg_get_userbyid(m.member) = NEW.role_name
          AND granted_role.rolname <> CASE
              WHEN v_runtime THEN 'factory_runtime'::NAME
              ELSE 'factory_approval_authority'::NAME
          END
    ) THEN
        RAISE EXCEPTION 'project identity has an unexpected role membership';
    END IF;
    RETURN NEW;
END;
$identity$;

CREATE TRIGGER project_identity_validate
    BEFORE INSERT OR UPDATE ON factory.project_identities
    FOR EACH ROW EXECUTE FUNCTION factory.validate_project_identity();

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
    approval_scope JSONB NOT NULL DEFAULT '{}'::jsonb
        CHECK (jsonb_typeof(approval_scope) = 'object'),
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
    idempotency_key TEXT NOT NULL DEFAULT gen_random_uuid()::text,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (task_id, attempt_number),
    UNIQUE (task_id, idempotency_key),
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
    attempt_id UUID NOT NULL,
    approval_round INTEGER NOT NULL CHECK (approval_round > 0),
    action TEXT NOT NULL CHECK (length(trim(action)) BETWEEN 1 AND 120),
    decision TEXT NOT NULL CHECK (decision IN ('approved', 'rejected')),
    decided_by TEXT NOT NULL CHECK (length(trim(decided_by)) BETWEEN 1 AND 200),
    rationale TEXT NOT NULL CHECK (length(trim(rationale)) BETWEEN 1 AND 4000),
    decision_scope JSONB NOT NULL DEFAULT '{}'::jsonb
        CHECK (jsonb_typeof(decision_scope) = 'object'),
    decided_by_login NAME NOT NULL DEFAULT session_user,
    decided_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (task_id, action, attempt_id),
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
        REFERENCES factory.task_artifacts(artifact_id, task_id, attempt_id) ON DELETE RESTRICT,
    UNIQUE (task_id, attempt_id, artifact_id, evidence_type)
);

CREATE FUNCTION factory.reject_immutable_row_mutation()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE EXCEPTION 'Rows in %.% are append-only', TG_TABLE_SCHEMA, TG_TABLE_NAME;
END;
$$;

CREATE TRIGGER product_dossier_versions_append_only
    BEFORE UPDATE OR DELETE ON factory.product_dossier_versions
    FOR EACH ROW EXECUTE FUNCTION factory.reject_immutable_row_mutation();
CREATE TRIGGER product_dossier_versions_no_truncate
    BEFORE TRUNCATE ON factory.product_dossier_versions
    FOR EACH STATEMENT EXECUTE FUNCTION factory.reject_immutable_row_mutation();

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
    v_project_id UUID;
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

    IF NOT pg_catalog.pg_has_role(session_user, 'factory_runtime', 'MEMBER')
       OR pg_catalog.pg_has_role(session_user, 'factory_approval_authority', 'MEMBER')
       OR pg_catalog.pg_has_role(session_user, 'factory_executor_owner', 'MEMBER') THEN
        RAISE EXCEPTION 'session identity is not an isolated project runtime role';
    END IF;

    SELECT project_id INTO v_project_id
    FROM factory.project_identities
    WHERE role_name = session_user AND identity_kind = 'runtime';
    IF NOT FOUND OR v_task.project_id <> v_project_id THEN
        RAISE EXCEPTION 'task not found for this product runtime';
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

    IF p_attempt_id IS NOT NULL AND NOT EXISTS (
        SELECT 1 FROM factory.task_attempts
        WHERE attempt_id = p_attempt_id AND task_id = p_task_id
    ) THEN
        RAISE EXCEPTION 'attempt does not belong to task';
    END IF;

    IF v_task.status = 'planned' AND p_to_state = 'implementing'
       AND v_task.approval_required
       AND (p_attempt_id IS NULL OR NOT EXISTS (
           SELECT 1 FROM factory.task_approvals
           WHERE task_id = p_task_id
             AND attempt_id = p_attempt_id
             AND action = 'begin_implementation'
             AND decision = 'approved'
             AND decision_scope = v_task.approval_scope
       )) THEN
        RAISE EXCEPTION 'human approval required for this attempt and decision scope';
    END IF;

    v_required_evidence := CASE
        WHEN v_task.status = 'testing' AND p_to_state = 'review' THEN 'test_report'
        WHEN v_task.status = 'review' AND p_to_state = 'candidate' THEN 'review_report'
        WHEN v_task.status = 'deployed_test' AND p_to_state = 'verified' THEN 'health_check'
        ELSE NULL
    END;

    IF v_required_evidence IS NOT NULL AND (
        p_attempt_id IS NULL OR NOT EXISTS (
            SELECT 1
            FROM factory.task_evidence e
            WHERE e.task_id = p_task_id
              AND e.evidence_type = v_required_evidence
              AND e.attempt_id = p_attempt_id
        )
    ) THEN
        RAISE EXCEPTION 'required evidence missing for the specified attempt: %', v_required_evidence;
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


-- Controlled task creation API. Project identity is derived only from session_user.
CREATE FUNCTION factory.create_task(
    p_task_key TEXT,
    p_title TEXT,
    p_request_text TEXT,
    p_acceptance_criteria JSONB,
    p_risk_class TEXT DEFAULT 'low',
    p_approval_required BOOLEAN DEFAULT FALSE,
    p_approval_scope JSONB DEFAULT '{}'::jsonb
)
RETURNS UUID
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, factory, pg_temp
AS $create_task$
DECLARE
    v_project_id UUID;
    v_task factory.tasks%ROWTYPE;
    v_task_id UUID;
BEGIN
    IF p_task_key IS NULL OR length(trim(p_task_key)) NOT BETWEEN 1 AND 120
       OR p_title IS NULL OR length(trim(p_title)) NOT BETWEEN 1 AND 160
       OR p_request_text IS NULL OR length(trim(p_request_text)) NOT BETWEEN 1 AND 12000
       OR p_acceptance_criteria IS NULL OR jsonb_typeof(p_acceptance_criteria) <> 'array'
       OR jsonb_array_length(p_acceptance_criteria) NOT BETWEEN 1 AND 30
       OR p_risk_class IS NULL OR p_risk_class NOT IN ('low','medium','high','critical')
       OR p_approval_required IS NULL
       OR p_approval_scope IS NULL OR jsonb_typeof(p_approval_scope) <> 'object'
       OR (p_risk_class IN ('high','critical') AND NOT p_approval_required) THEN
        RAISE EXCEPTION 'invalid task creation arguments';
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

    PERFORM pg_catalog.pg_advisory_xact_lock(
        pg_catalog.hashtextextended(v_project_id::text || ':' || p_task_key, 0)
    );

    SELECT * INTO v_task
    FROM factory.tasks
    WHERE project_id = v_project_id AND task_key = p_task_key
    FOR UPDATE;

    IF FOUND THEN
        IF v_task.title = p_title
           AND v_task.request_text = p_request_text
           AND v_task.acceptance_criteria = p_acceptance_criteria
           AND v_task.risk_class = p_risk_class
           AND v_task.approval_required = p_approval_required
           AND v_task.approval_scope = p_approval_scope THEN
            RETURN v_task.task_id;
        END IF;
        RAISE EXCEPTION 'task_key already exists with different task definition';
    END IF;

    INSERT INTO factory.tasks (
        project_id, task_key, title, request_text, acceptance_criteria,
        risk_class, approval_required, approval_scope
    ) VALUES (
        v_project_id, p_task_key, p_title, p_request_text, p_acceptance_criteria,
        p_risk_class, p_approval_required, p_approval_scope
    ) RETURNING task_id INTO v_task_id;

    RETURN v_task_id;
END;
$create_task$;


-- Attempt creation is idempotent and serializes attempt numbering per task.
CREATE FUNCTION factory.create_task_attempt(
    p_task_id UUID,
    p_idempotency_key TEXT,
    p_worker_role TEXT DEFAULT 'implementer',
    p_branch_name TEXT DEFAULT NULL,
    p_metadata JSONB DEFAULT '{}'::jsonb
)
RETURNS UUID
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, factory, pg_temp
AS $create_attempt$
DECLARE
    v_project_id UUID;
    v_task factory.tasks%ROWTYPE;
    v_attempt factory.task_attempts%ROWTYPE;
    v_attempt_id UUID;
    v_next_number INTEGER;
BEGIN
    IF p_task_id IS NULL
       OR p_idempotency_key IS NULL OR length(trim(p_idempotency_key)) NOT BETWEEN 1 AND 255
       OR p_worker_role IS NULL OR p_worker_role NOT IN ('planner','implementer','tester','reviewer','release','observer')
       OR (p_branch_name IS NOT NULL AND length(trim(p_branch_name)) NOT BETWEEN 1 AND 255)
       OR p_metadata IS NULL OR jsonb_typeof(p_metadata) <> 'object' THEN
        RAISE EXCEPTION 'invalid task attempt arguments';
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

    SELECT * INTO v_task FROM factory.tasks
    WHERE task_id = p_task_id AND project_id = v_project_id
    FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'task not found for this product runtime';
    END IF;

    SELECT * INTO v_attempt FROM factory.task_attempts
    WHERE task_id = p_task_id AND idempotency_key = p_idempotency_key;
    IF FOUND THEN
        IF v_attempt.worker_role = p_worker_role
           AND v_attempt.branch_name IS NOT DISTINCT FROM p_branch_name
           AND v_attempt.metadata = p_metadata THEN
            RETURN v_attempt.attempt_id;
        END IF;
        RAISE EXCEPTION 'attempt idempotency key reused with different intent';
    END IF;

    SELECT COALESCE(MAX(attempt_number), 0) + 1 INTO v_next_number
    FROM factory.task_attempts WHERE task_id = p_task_id;

    INSERT INTO factory.task_attempts (
        task_id, attempt_number, worker_role, status, branch_name,
        started_at, metadata, idempotency_key
    ) VALUES (
        p_task_id, v_next_number, p_worker_role, 'running', p_branch_name,
        now(), p_metadata, p_idempotency_key
    ) RETURNING attempt_id INTO v_attempt_id;

    RETURN v_attempt_id;
END;
$create_attempt$;


-- One atomic, idempotent path records an artifact and its typed evidence.
CREATE FUNCTION factory.record_task_evidence(
    p_task_id UUID,
    p_attempt_id UUID,
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
AS $record_evidence$
DECLARE
    v_project_id UUID;
    v_artifact_id UUID;
    v_existing factory.task_artifacts%ROWTYPE;
BEGIN
    IF p_task_id IS NULL OR p_attempt_id IS NULL
       OR p_artifact_type IS NULL OR length(trim(p_artifact_type)) NOT BETWEEN 1 AND 80
       OR p_object_uri IS NULL OR length(trim(p_object_uri)) NOT BETWEEN 1 AND 2048
       OR p_sha256 IS NULL OR length(p_sha256) <> 64 OR p_sha256 ~ '[^0-9a-f]'
       OR p_byte_size IS NULL OR p_byte_size < 0
       OR p_content_type IS NULL OR length(trim(p_content_type)) NOT BETWEEN 1 AND 255
       OR p_evidence_type IS NULL OR length(trim(p_evidence_type)) NOT BETWEEN 1 AND 100
       OR p_description IS NULL OR length(p_description) > 4000
       OR p_metadata IS NULL OR jsonb_typeof(p_metadata) <> 'object' THEN
        RAISE EXCEPTION 'invalid task evidence arguments';
    END IF;

    IF NOT pg_catalog.pg_has_role(session_user, 'factory_runtime', 'MEMBER')
       OR pg_catalog.pg_has_role(session_user, 'factory_approval_authority', 'MEMBER')
       OR pg_catalog.pg_has_role(session_user, 'factory_executor_owner', 'MEMBER') THEN
        RAISE EXCEPTION 'session identity is not an isolated product runtime';
    END IF;

    SELECT project_id INTO v_project_id
    FROM factory.project_identities
    WHERE role_name = session_user AND identity_kind = 'runtime';
    IF NOT FOUND OR NOT EXISTS (
        SELECT 1 FROM factory.tasks
        WHERE task_id = p_task_id AND project_id = v_project_id
    ) OR NOT EXISTS (
        SELECT 1 FROM factory.task_attempts
        WHERE task_id = p_task_id AND attempt_id = p_attempt_id
    ) THEN
        RAISE EXCEPTION 'task attempt is not owned by this product runtime';
    END IF;

    INSERT INTO factory.task_artifacts (
        task_id, attempt_id, artifact_type, object_uri, sha256, byte_size, content_type
    ) VALUES (
        p_task_id, p_attempt_id, p_artifact_type, p_object_uri, p_sha256,
        p_byte_size, p_content_type
    )
    ON CONFLICT (task_id, object_uri, sha256) DO NOTHING;

    SELECT * INTO v_existing
    FROM factory.task_artifacts
    WHERE task_id = p_task_id AND object_uri = p_object_uri AND sha256 = p_sha256;
    IF NOT FOUND OR v_existing.attempt_id IS DISTINCT FROM p_attempt_id
       OR v_existing.artifact_type <> p_artifact_type
       OR v_existing.byte_size <> p_byte_size
       OR v_existing.content_type <> p_content_type THEN
        RAISE EXCEPTION 'artifact identity conflicts with existing record';
    END IF;
    v_artifact_id := v_existing.artifact_id;

    INSERT INTO factory.task_evidence (
        task_id, attempt_id, artifact_id, evidence_type, description,
        recorded_by, metadata
    ) VALUES (
        p_task_id, p_attempt_id, v_artifact_id, p_evidence_type, p_description,
        session_user::text, p_metadata
    )
    ON CONFLICT (task_id, attempt_id, artifact_id, evidence_type) DO NOTHING;

    RETURN v_artifact_id;
END;
$record_evidence$;


CREATE FUNCTION factory.finish_task_attempt(
    p_task_id UUID,
    p_attempt_id UUID,
    p_outcome TEXT
)
RETURNS TEXT
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, factory, pg_temp
AS $finish_attempt$
DECLARE
    v_project_id UUID;
    v_attempt factory.task_attempts%ROWTYPE;
BEGIN
    IF p_task_id IS NULL OR p_attempt_id IS NULL
       OR p_outcome IS NULL OR p_outcome NOT IN ('succeeded','failed') THEN
        RAISE EXCEPTION 'invalid attempt completion arguments';
    END IF;
    IF NOT pg_catalog.pg_has_role(session_user, 'factory_runtime', 'MEMBER')
       OR pg_catalog.pg_has_role(session_user, 'factory_approval_authority', 'MEMBER')
       OR pg_catalog.pg_has_role(session_user, 'factory_executor_owner', 'MEMBER') THEN
        RAISE EXCEPTION 'session identity is not an isolated product runtime';
    END IF;
    SELECT project_id INTO v_project_id FROM factory.project_identities
    WHERE role_name = session_user AND identity_kind = 'runtime';
    IF NOT FOUND THEN
        RAISE EXCEPTION 'runtime identity has no product mapping';
    END IF;

    SELECT a.* INTO v_attempt
    FROM factory.task_attempts a
    JOIN factory.tasks t ON t.task_id = a.task_id
    WHERE a.task_id = p_task_id AND a.attempt_id = p_attempt_id
      AND t.project_id = v_project_id
    FOR UPDATE OF a;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'attempt not found for this product runtime';
    END IF;
    IF v_attempt.status = p_outcome THEN
        RETURN v_attempt.status;
    END IF;
    IF v_attempt.status <> 'running' THEN
        RAISE EXCEPTION 'only a running attempt can be completed';
    END IF;

    UPDATE factory.task_attempts
    SET status = p_outcome, finished_at = now()
    WHERE task_id = p_task_id AND attempt_id = p_attempt_id;
    RETURN p_outcome;
END;
$finish_attempt$;


-- Controlled dossier write path. Each call appends one immutable snapshot.
CREATE FUNCTION factory.record_product_dossier(
    p_project_id UUID,
    p_dossier JSONB,
    p_idempotency_key TEXT
)
RETURNS INTEGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, factory, pg_temp
AS $dossier$
DECLARE
    v_product_type TEXT;
    v_existing factory.product_dossier_versions%ROWTYPE;
    v_next_version INTEGER;
BEGIN
    IF p_project_id IS NULL
       OR p_dossier IS NULL OR jsonb_typeof(p_dossier) <> 'object'
       OR p_idempotency_key IS NULL
       OR length(trim(p_idempotency_key)) NOT BETWEEN 1 AND 255 THEN
        RAISE EXCEPTION 'invalid product dossier arguments';
    END IF;

    IF NOT pg_catalog.pg_has_role(session_user, 'factory_runtime', 'MEMBER')
       OR pg_catalog.pg_has_role(session_user, 'factory_approval_authority', 'MEMBER')
       OR pg_catalog.pg_has_role(session_user, 'factory_executor_owner', 'MEMBER')
       OR NOT EXISTS (
           SELECT 1 FROM factory.project_identities
           WHERE role_name = session_user AND project_id = p_project_id
       ) THEN
        RAISE EXCEPTION 'session identity is not authorized for this product dossier';
    END IF;

    IF p_dossier->>'schema_version' IS DISTINCT FROM '1'
       OR jsonb_typeof(p_dossier->'product_type') IS DISTINCT FROM 'string'
       OR length(trim(p_dossier->>'product_type')) NOT BETWEEN 1 AND 80
       OR jsonb_typeof(p_dossier->'mission') IS DISTINCT FROM 'string'
       OR length(trim(p_dossier->>'mission')) NOT BETWEEN 1 AND 12000
       OR jsonb_typeof(p_dossier->'requirements') IS DISTINCT FROM 'array'
       OR jsonb_array_length(p_dossier->'requirements') < 1
       OR jsonb_typeof(p_dossier->'acceptance_criteria') IS DISTINCT FROM 'array'
       OR jsonb_array_length(p_dossier->'acceptance_criteria') < 1
       OR jsonb_typeof(p_dossier->'lifecycle') IS DISTINCT FROM 'object' THEN
        RAISE EXCEPTION 'product dossier does not satisfy the minimum schema';
    END IF;

    PERFORM pg_catalog.pg_advisory_xact_lock(pg_catalog.hashtextextended(p_project_id::text, 0));

    SELECT product_type INTO v_product_type
    FROM factory.projects
    WHERE project_id = p_project_id;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'product not found or not visible to this identity';
    END IF;

    IF p_dossier->>'product_type' IS DISTINCT FROM v_product_type THEN
        RAISE EXCEPTION 'dossier product_type does not match the registered product';
    END IF;

    SELECT * INTO v_existing
    FROM factory.product_dossier_versions
    WHERE project_id = p_project_id AND idempotency_key = p_idempotency_key;

    IF FOUND THEN
        IF v_existing.dossier = p_dossier THEN
            RETURN v_existing.version_no;
        END IF;
        RAISE EXCEPTION 'dossier idempotency key reused with different content';
    END IF;

    SELECT COALESCE(MAX(version_no), 0) + 1 INTO v_next_version
    FROM factory.product_dossier_versions
    WHERE project_id = p_project_id;

    INSERT INTO factory.product_dossier_versions (
        project_id, version_no, idempotency_key, dossier, created_by_login
    ) VALUES (
        p_project_id, v_next_version, p_idempotency_key, p_dossier, session_user
    );

    RETURN v_next_version;
END;
$dossier$;

-- Runtime table access remains read-only. Narrow SECURITY DEFINER functions
-- provide dossier, task, attempt, evidence, and lifecycle writes. Cluster roles
-- are provisioned separately by
-- migrations/bootstrap/0001_factory_roles.sql. The schema migration identity
-- must be granted SET (but not INHERIT) membership in factory_executor_owner.
DO $role_preflight$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles
        WHERE rolname = 'factory_executor_owner'
          AND NOT rolcanlogin AND NOT rolinherit AND NOT rolsuper
          AND NOT rolcreatedb AND NOT rolcreaterole AND NOT rolbypassrls
    ) THEN
        RAISE EXCEPTION 'factory_executor_owner missing or has unsafe attributes; run the role bootstrap';
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles
        WHERE rolname = 'factory_runtime'
          AND NOT rolcanlogin AND NOT rolinherit AND NOT rolsuper
          AND NOT rolcreatedb AND NOT rolcreaterole AND NOT rolbypassrls
    ) THEN
        RAISE EXCEPTION 'factory_runtime missing or has unsafe attributes; run the role bootstrap';
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles
        WHERE rolname = 'factory_approval_authority'
          AND NOT rolcanlogin AND NOT rolinherit AND NOT rolsuper
          AND NOT rolcreatedb AND NOT rolcreaterole AND NOT rolbypassrls
    ) OR NOT EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles
        WHERE rolname = 'factory_identity_admin'
          AND NOT rolcanlogin AND NOT rolinherit AND NOT rolsuper
          AND NOT rolcreatedb AND NOT rolcreaterole AND NOT rolbypassrls
    ) THEN
        RAISE EXCEPTION 'approval or identity-admin role missing or unsafe; run the role bootstrap';
    END IF;

    IF NOT pg_catalog.pg_has_role(CURRENT_USER, 'factory_executor_owner', 'SET') THEN
        RAISE EXCEPTION 'migration identity must have SET membership in factory_executor_owner';
    END IF;

    IF pg_catalog.pg_has_role('factory_runtime', 'factory_executor_owner', 'MEMBER') THEN
        RAISE EXCEPTION 'factory_runtime must never be a member of factory_executor_owner';
    END IF;
    IF pg_catalog.pg_has_role('factory_runtime', 'factory_approval_authority', 'MEMBER') THEN
        RAISE EXCEPTION 'factory_runtime must never be a member of factory_approval_authority';
    END IF;
    IF pg_catalog.pg_has_role('factory_runtime', 'factory_identity_admin', 'MEMBER')
       OR pg_catalog.pg_has_role('factory_approval_authority', 'factory_identity_admin', 'MEMBER') THEN
        RAISE EXCEPTION 'runtime and approval authority must not be members of factory_identity_admin';
    END IF;
    IF pg_catalog.pg_has_role('factory_identity_admin', 'factory_runtime', 'MEMBER')
       OR pg_catalog.pg_has_role('factory_identity_admin', 'factory_approval_authority', 'MEMBER')
       OR pg_catalog.pg_has_role('factory_identity_admin', 'factory_executor_owner', 'MEMBER') THEN
        RAISE EXCEPTION 'factory_identity_admin must remain a separate authority';
    END IF;
END
$role_preflight$;

REVOKE ALL ON SCHEMA factory FROM PUBLIC;
REVOKE CREATE ON SCHEMA factory FROM PUBLIC;
GRANT USAGE ON SCHEMA factory TO factory_runtime;
GRANT USAGE ON SCHEMA factory TO factory_approval_authority;
GRANT USAGE ON SCHEMA factory TO factory_identity_admin;
GRANT SELECT, INSERT, UPDATE ON factory.projects TO factory_identity_admin;
GRANT SELECT, INSERT, UPDATE ON factory.project_identities TO factory_identity_admin;

REVOKE ALL ON ALL TABLES IN SCHEMA factory FROM PUBLIC;
REVOKE ALL ON ALL SEQUENCES IN SCHEMA factory FROM PUBLIC;
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA factory FROM PUBLIC;

GRANT SELECT ON ALL TABLES IN SCHEMA factory TO factory_runtime;
GRANT INSERT ON factory.task_approvals TO factory_approval_authority;
GRANT SELECT ON factory.project_identities, factory.tasks TO factory_approval_authority;
REVOKE INSERT, UPDATE, DELETE, TRUNCATE, REFERENCES, TRIGGER
    ON ALL TABLES IN SCHEMA factory FROM factory_runtime;
REVOKE ALL ON ALL SEQUENCES IN SCHEMA factory FROM factory_runtime;

-- Give the SECURITY DEFINER function a dedicated, non-login owner with
-- only the table privileges its body requires. It is not a superuser or table owner.
GRANT USAGE, CREATE ON SCHEMA factory TO factory_executor_owner;
GRANT SELECT ON factory.projects TO factory_executor_owner;
GRANT SELECT, INSERT, UPDATE ON factory.tasks TO factory_executor_owner;
GRANT SELECT, INSERT ON factory.task_events TO factory_executor_owner;
GRANT SELECT, INSERT ON factory.product_dossier_versions TO factory_executor_owner;
GRANT SELECT ON factory.task_approvals, factory.project_identities TO factory_executor_owner;
GRANT SELECT, INSERT, UPDATE ON factory.task_attempts TO factory_executor_owner;
GRANT SELECT, INSERT ON factory.task_artifacts, factory.task_evidence TO factory_executor_owner;

REVOKE ALL ON FUNCTION factory.record_product_dossier(UUID, JSONB, TEXT) FROM PUBLIC;
REVOKE ALL ON FUNCTION factory.record_product_dossier(UUID, JSONB, TEXT) FROM factory_runtime;
GRANT EXECUTE ON FUNCTION factory.record_product_dossier(UUID, JSONB, TEXT) TO factory_runtime;
ALTER FUNCTION factory.record_product_dossier(UUID, JSONB, TEXT) OWNER TO factory_executor_owner;

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
-- Controlled runtime writes are exposed only through these SECURITY DEFINER functions.
REVOKE ALL ON FUNCTION factory.create_task(TEXT, TEXT, TEXT, JSONB, TEXT, BOOLEAN, JSONB) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION factory.create_task(TEXT, TEXT, TEXT, JSONB, TEXT, BOOLEAN, JSONB) TO factory_runtime;
ALTER FUNCTION factory.create_task(TEXT, TEXT, TEXT, JSONB, TEXT, BOOLEAN, JSONB) OWNER TO factory_executor_owner;

REVOKE ALL ON FUNCTION factory.create_task_attempt(UUID, TEXT, TEXT, TEXT, JSONB) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION factory.create_task_attempt(UUID, TEXT, TEXT, TEXT, JSONB) TO factory_runtime;
ALTER FUNCTION factory.create_task_attempt(UUID, TEXT, TEXT, TEXT, JSONB) OWNER TO factory_executor_owner;

REVOKE ALL ON FUNCTION factory.record_task_evidence(UUID, UUID, TEXT, TEXT, TEXT, BIGINT, TEXT, TEXT, TEXT, JSONB) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION factory.record_task_evidence(UUID, UUID, TEXT, TEXT, TEXT, BIGINT, TEXT, TEXT, TEXT, JSONB) TO factory_runtime;
ALTER FUNCTION factory.record_task_evidence(UUID, UUID, TEXT, TEXT, TEXT, BIGINT, TEXT, TEXT, TEXT, JSONB) OWNER TO factory_executor_owner;

REVOKE ALL ON FUNCTION factory.finish_task_attempt(UUID, UUID, TEXT) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION factory.finish_task_attempt(UUID, UUID, TEXT) TO factory_runtime;
ALTER FUNCTION factory.finish_task_attempt(UUID, UUID, TEXT) OWNER TO factory_executor_owner;

REVOKE CREATE ON SCHEMA factory FROM factory_executor_owner;

-- Project isolation is enforced by database login identity, not caller-settable
-- session variables. Every project-specific LOGIN role must be explicitly mapped
-- by an administrator and must not be shared between projects.
ALTER TABLE factory.product_dossier_versions ENABLE ROW LEVEL SECURITY;
ALTER TABLE factory.product_dossier_versions FORCE ROW LEVEL SECURITY;
ALTER TABLE factory.projects ENABLE ROW LEVEL SECURITY;
ALTER TABLE factory.projects FORCE ROW LEVEL SECURITY;
ALTER TABLE factory.project_identities ENABLE ROW LEVEL SECURITY;
ALTER TABLE factory.project_identities FORCE ROW LEVEL SECURITY;
ALTER TABLE factory.tasks ENABLE ROW LEVEL SECURITY;
ALTER TABLE factory.tasks FORCE ROW LEVEL SECURITY;
ALTER TABLE factory.task_attempts ENABLE ROW LEVEL SECURITY;
ALTER TABLE factory.task_attempts FORCE ROW LEVEL SECURITY;
ALTER TABLE factory.task_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE factory.task_events FORCE ROW LEVEL SECURITY;
ALTER TABLE factory.task_approvals ENABLE ROW LEVEL SECURITY;
ALTER TABLE factory.task_approvals FORCE ROW LEVEL SECURITY;
ALTER TABLE factory.task_artifacts ENABLE ROW LEVEL SECURITY;
ALTER TABLE factory.task_artifacts FORCE ROW LEVEL SECURITY;
ALTER TABLE factory.task_evidence ENABLE ROW LEVEL SECURITY;
ALTER TABLE factory.task_evidence FORCE ROW LEVEL SECURITY;

CREATE POLICY projects_admin_manage ON factory.projects
    FOR ALL TO factory_identity_admin
    USING (true)
    WITH CHECK (true);
CREATE POLICY project_identity_admin_manage ON factory.project_identities
    FOR ALL TO factory_identity_admin
    USING (true)
    WITH CHECK (true);
CREATE POLICY project_identity_self ON factory.project_identities
    FOR SELECT TO PUBLIC
    USING (
        role_name = session_user
        AND (
            (
                pg_catalog.pg_has_role(session_user, 'factory_runtime', 'MEMBER')
                AND NOT pg_catalog.pg_has_role(session_user, 'factory_approval_authority', 'MEMBER')
                AND NOT pg_catalog.pg_has_role(session_user, 'factory_executor_owner', 'MEMBER')
                AND NOT EXISTS (
                    SELECT 1
                    FROM pg_catalog.pg_auth_members m
                    JOIN pg_catalog.pg_roles granted_role ON granted_role.oid = m.roleid
                    WHERE pg_catalog.pg_get_userbyid(m.member) = session_user
                      AND granted_role.rolname <> 'factory_runtime'
                )
            )
            OR
            (
                pg_catalog.pg_has_role(session_user, 'factory_approval_authority', 'MEMBER')
                AND NOT pg_catalog.pg_has_role(session_user, 'factory_runtime', 'MEMBER')
                AND NOT pg_catalog.pg_has_role(session_user, 'factory_executor_owner', 'MEMBER')
                AND NOT EXISTS (
                    SELECT 1
                    FROM pg_catalog.pg_auth_members m
                    JOIN pg_catalog.pg_roles granted_role ON granted_role.oid = m.roleid
                    WHERE pg_catalog.pg_get_userbyid(m.member) = session_user
                      AND granted_role.rolname <> 'factory_approval_authority'
                )
            )
        )
    );
CREATE POLICY product_dossiers_isolated ON factory.product_dossier_versions
    FOR SELECT TO PUBLIC
    USING (project_id IN (
        SELECT project_id FROM factory.project_identities
        WHERE role_name = session_user
    ));
CREATE POLICY product_dossiers_insert ON factory.product_dossier_versions
    FOR INSERT TO factory_executor_owner
    WITH CHECK (project_id IN (
        SELECT project_id FROM factory.project_identities
        WHERE role_name = session_user
    ));
CREATE POLICY projects_isolated ON factory.projects
    FOR SELECT TO PUBLIC
    USING (project_id IN (
        SELECT project_id FROM factory.project_identities
        WHERE role_name = session_user
    ));
CREATE POLICY tasks_isolated ON factory.tasks
    FOR SELECT TO PUBLIC
    USING (project_id IN (
        SELECT project_id FROM factory.project_identities
        WHERE role_name = session_user
    ));
CREATE POLICY tasks_executor_insert ON factory.tasks
    FOR INSERT TO factory_executor_owner
    WITH CHECK (project_id IN (
        SELECT project_id FROM factory.project_identities
        WHERE role_name = session_user
    ));
CREATE POLICY tasks_transition_update ON factory.tasks
    FOR UPDATE TO factory_executor_owner
    USING (project_id IN (
        SELECT project_id FROM factory.project_identities
        WHERE role_name = session_user
    ))
    WITH CHECK (project_id IN (
        SELECT project_id FROM factory.project_identities
        WHERE role_name = session_user
    ));
CREATE POLICY attempts_isolated ON factory.task_attempts
    FOR SELECT TO PUBLIC
    USING (task_id IN (SELECT task_id FROM factory.tasks));
CREATE POLICY attempts_executor_insert ON factory.task_attempts
    FOR INSERT TO factory_executor_owner
    WITH CHECK (task_id IN (SELECT task_id FROM factory.tasks));
CREATE POLICY attempts_executor_update ON factory.task_attempts
    FOR UPDATE TO factory_executor_owner
    USING (task_id IN (SELECT task_id FROM factory.tasks))
    WITH CHECK (task_id IN (SELECT task_id FROM factory.tasks));
CREATE POLICY events_isolated ON factory.task_events
    FOR SELECT TO PUBLIC
    USING (task_id IN (SELECT task_id FROM factory.tasks));
CREATE POLICY events_transition_insert ON factory.task_events
    FOR INSERT TO factory_executor_owner
    WITH CHECK (task_id IN (SELECT task_id FROM factory.tasks));
CREATE POLICY approvals_isolated ON factory.task_approvals
    FOR SELECT TO PUBLIC
    USING (task_id IN (SELECT task_id FROM factory.tasks));
CREATE POLICY approvals_human_insert ON factory.task_approvals
    FOR INSERT TO factory_approval_authority
    WITH CHECK (task_id IN (SELECT task_id FROM factory.tasks));
CREATE FUNCTION factory.validate_human_approval_identity()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path = pg_catalog, factory, pg_temp
AS $approval_identity$
BEGIN
    IF NOT pg_catalog.pg_has_role(session_user, 'factory_approval_authority', 'MEMBER')
       OR pg_catalog.pg_has_role(session_user, 'factory_runtime', 'MEMBER')
       OR pg_catalog.pg_has_role(session_user, 'factory_executor_owner', 'MEMBER') THEN
        RAISE EXCEPTION 'approval must be recorded by an isolated human-approval login';
    END IF;
    RETURN NEW;
END;
$approval_identity$;

CREATE TRIGGER task_approval_identity_guard
    BEFORE INSERT ON factory.task_approvals
    FOR EACH ROW EXECUTE FUNCTION factory.validate_human_approval_identity();
CREATE POLICY artifacts_isolated ON factory.task_artifacts
    FOR SELECT TO PUBLIC
    USING (task_id IN (SELECT task_id FROM factory.tasks));
CREATE POLICY artifacts_executor_insert ON factory.task_artifacts
    FOR INSERT TO factory_executor_owner
    WITH CHECK (task_id IN (SELECT task_id FROM factory.tasks));
CREATE POLICY evidence_isolated ON factory.task_evidence
    FOR SELECT TO PUBLIC
    USING (task_id IN (SELECT task_id FROM factory.tasks));
CREATE POLICY evidence_executor_insert ON factory.task_evidence
    FOR INSERT TO factory_executor_owner
    WITH CHECK (task_id IN (SELECT task_id FROM factory.tasks));

REVOKE ALL ON FUNCTION factory.validate_project_identity() FROM PUBLIC;
REVOKE ALL ON FUNCTION factory.validate_human_approval_identity() FROM PUBLIC;

-- Future objects created by the migration owner inherit the same safe defaults.
ALTER DEFAULT PRIVILEGES FOR ROLE CURRENT_USER IN SCHEMA factory
    REVOKE ALL ON TABLES FROM PUBLIC;
ALTER DEFAULT PRIVILEGES FOR ROLE CURRENT_USER IN SCHEMA factory
    GRANT SELECT ON TABLES TO factory_runtime;
ALTER DEFAULT PRIVILEGES FOR ROLE CURRENT_USER IN SCHEMA factory
    REVOKE EXECUTE ON FUNCTIONS FROM PUBLIC;

COMMIT;
