-- DRAFT ONLY — NOT APPROVED FOR EXECUTION.
-- Target: an isolated Neon branch created specifically for factory schema testing.
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
    UNIQUE (task_id, attempt_number)
);

CREATE TABLE factory.task_events (
    event_seq BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    event_id UUID NOT NULL DEFAULT gen_random_uuid() UNIQUE,
    task_id UUID NOT NULL REFERENCES factory.tasks(task_id) ON DELETE RESTRICT,
    attempt_id UUID REFERENCES factory.task_attempts(attempt_id) ON DELETE RESTRICT,
    event_type TEXT NOT NULL CHECK (length(trim(event_type)) BETWEEN 1 AND 100),
    from_state TEXT,
    to_state TEXT,
    actor_type TEXT NOT NULL CHECK (actor_type IN ('human', 'system', 'agent', 'github')),
    actor_ref TEXT NOT NULL CHECK (length(trim(actor_ref)) BETWEEN 1 AND 200),
    idempotency_key TEXT NOT NULL UNIQUE,
    payload JSONB NOT NULL DEFAULT '{}'::jsonb
        CHECK (jsonb_typeof(payload) = 'object'),
    occurred_at TIMESTAMPTZ,
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX task_events_task_seq_idx
    ON factory.task_events (task_id, event_seq);

CREATE TABLE factory.task_approvals (
    approval_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    task_id UUID NOT NULL REFERENCES factory.tasks(task_id) ON DELETE RESTRICT,
    attempt_id UUID REFERENCES factory.task_attempts(attempt_id) ON DELETE RESTRICT,
    approval_round INTEGER NOT NULL CHECK (approval_round > 0),
    action TEXT NOT NULL CHECK (length(trim(action)) BETWEEN 1 AND 120),
    decision TEXT NOT NULL CHECK (decision IN ('approved', 'rejected')),
    decided_by TEXT NOT NULL CHECK (length(trim(decided_by)) BETWEEN 1 AND 200),
    rationale TEXT NOT NULL CHECK (length(trim(rationale)) BETWEEN 1 AND 4000),
    decision_scope JSONB NOT NULL DEFAULT '{}'::jsonb
        CHECK (jsonb_typeof(decision_scope) = 'object'),
    decided_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (task_id, action, approval_round)
);

CREATE TABLE factory.task_artifacts (
    artifact_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    task_id UUID NOT NULL REFERENCES factory.tasks(task_id) ON DELETE RESTRICT,
    attempt_id UUID REFERENCES factory.task_attempts(attempt_id) ON DELETE RESTRICT,
    artifact_type TEXT NOT NULL CHECK (length(trim(artifact_type)) BETWEEN 1 AND 80),
    object_uri TEXT NOT NULL CHECK (length(trim(object_uri)) BETWEEN 1 AND 2048),
    sha256 TEXT NOT NULL CHECK (sha256 ~ '^[0-9a-f]{64}$'),
    byte_size BIGINT NOT NULL CHECK (byte_size >= 0),
    content_type TEXT NOT NULL DEFAULT 'application/octet-stream',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (task_id, object_uri, sha256)
);

CREATE TABLE factory.task_evidence (
    evidence_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    task_id UUID NOT NULL REFERENCES factory.tasks(task_id) ON DELETE RESTRICT,
    attempt_id UUID REFERENCES factory.task_attempts(attempt_id) ON DELETE RESTRICT,
    artifact_id UUID NOT NULL REFERENCES factory.task_artifacts(artifact_id) ON DELETE RESTRICT,
    evidence_type TEXT NOT NULL CHECK (length(trim(evidence_type)) BETWEEN 1 AND 100),
    description TEXT NOT NULL DEFAULT '',
    recorded_by TEXT NOT NULL CHECK (length(trim(recorded_by)) BETWEEN 1 AND 200),
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb
        CHECK (jsonb_typeof(metadata) = 'object')
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

CREATE TRIGGER task_approvals_append_only
    BEFORE UPDATE OR DELETE ON factory.task_approvals
    FOR EACH ROW EXECUTE FUNCTION factory.reject_immutable_row_mutation();

CREATE TRIGGER task_evidence_append_only
    BEFORE UPDATE OR DELETE ON factory.task_evidence
    FOR EACH ROW EXECUTE FUNCTION factory.reject_immutable_row_mutation();

CREATE TRIGGER task_artifacts_append_only
    BEFORE UPDATE OR DELETE ON factory.task_artifacts
    FOR EACH ROW EXECUTE FUNCTION factory.reject_immutable_row_mutation();

REVOKE UPDATE, DELETE ON factory.task_events FROM PUBLIC;
REVOKE UPDATE, DELETE ON factory.task_approvals FROM PUBLIC;
REVOKE UPDATE, DELETE ON factory.task_evidence FROM PUBLIC;
REVOKE UPDATE, DELETE ON factory.task_artifacts FROM PUBLIC;

COMMIT;
