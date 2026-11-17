-- DRAFT ONLY — CI applies this to disposable PostgreSQL 17.
-- Persists the exact atomic intake package, then records an immutable decision.
-- Neither operation creates tasks, dispatches work, reserves resources, or deploys.
BEGIN;

-- A plan version must be uniquely addressable together with the mission version it describes.
ALTER TABLE factory.task_plan_versions
    ADD CONSTRAINT task_plan_versions_snapshot_identity_key
    UNIQUE (project_id, mission_id, mission_version_no, plan_version_no);

CREATE TABLE factory.intake_submissions (
    intake_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES factory.projects(project_id) ON DELETE RESTRICT,
    idempotency_key TEXT NOT NULL CHECK (length(trim(idempotency_key)) BETWEEN 1 AND 255),
    dossier_version_no INTEGER NOT NULL CHECK (dossier_version_no > 0),
    mission_id TEXT NOT NULL CHECK (length(trim(mission_id)) BETWEEN 1 AND 80),
    mission_version_no INTEGER NOT NULL CHECK (mission_version_no > 0),
    plan_version_no INTEGER NOT NULL CHECK (plan_version_no > 0),
    created_by_login NAME NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (project_id, idempotency_key),
    UNIQUE (project_id, intake_id),
    UNIQUE (
        project_id, mission_id,
        dossier_version_no, mission_version_no, plan_version_no
    ),
    FOREIGN KEY (project_id, dossier_version_no)
        REFERENCES factory.product_dossier_versions(project_id, version_no)
        ON DELETE RESTRICT,
    FOREIGN KEY (project_id, mission_id, mission_version_no)
        REFERENCES factory.mission_versions(project_id, mission_id, version_no)
        ON DELETE RESTRICT,
    FOREIGN KEY (
        project_id, mission_id, mission_version_no, plan_version_no
    ) REFERENCES factory.task_plan_versions(
        project_id, mission_id, mission_version_no, plan_version_no
    ) ON DELETE RESTRICT
);

CREATE INDEX intake_submissions_latest_idx
    ON factory.intake_submissions(project_id, created_at DESC);

CREATE TABLE factory.intake_approvals (
    approval_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL,
    intake_id UUID NOT NULL,
    decision TEXT NOT NULL CHECK (decision IN ('approved', 'rejected')),
    rationale TEXT NOT NULL CHECK (length(trim(rationale)) BETWEEN 1 AND 4000),
    idempotency_key TEXT NOT NULL CHECK (length(trim(idempotency_key)) BETWEEN 1 AND 255),
    decided_by_login NAME NOT NULL,
    decided_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (project_id, idempotency_key),
    UNIQUE (project_id, intake_id),
    FOREIGN KEY (project_id, intake_id)
        REFERENCES factory.intake_submissions(project_id, intake_id)
        ON DELETE RESTRICT
);

CREATE INDEX intake_approvals_project_time_idx
    ON factory.intake_approvals(project_id, decided_at DESC);

CREATE TRIGGER intake_submissions_append_only
    BEFORE UPDATE OR DELETE ON factory.intake_submissions
    FOR EACH ROW EXECUTE FUNCTION factory.reject_mission_plan_mutation();
CREATE TRIGGER intake_submissions_no_truncate
    BEFORE TRUNCATE ON factory.intake_submissions
    FOR EACH STATEMENT EXECUTE FUNCTION factory.reject_mission_plan_mutation();
CREATE TRIGGER intake_approvals_append_only
    BEFORE UPDATE OR DELETE ON factory.intake_approvals
    FOR EACH ROW EXECUTE FUNCTION factory.reject_mission_plan_mutation();
CREATE TRIGGER intake_approvals_no_truncate
    BEFORE TRUNCATE ON factory.intake_approvals
    FOR EACH STATEMENT EXECUTE FUNCTION factory.reject_mission_plan_mutation();

REVOKE ALL ON factory.intake_submissions, factory.intake_approvals FROM PUBLIC;
REVOKE UPDATE, DELETE, TRUNCATE ON factory.intake_submissions, factory.intake_approvals
    FROM factory_runtime, factory_approval_authority;
REVOKE INSERT ON factory.intake_submissions, factory.intake_approvals
    FROM factory_runtime, factory_approval_authority;

ALTER TABLE factory.intake_submissions ENABLE ROW LEVEL SECURITY;
ALTER TABLE factory.intake_submissions FORCE ROW LEVEL SECURITY;
ALTER TABLE factory.intake_approvals ENABLE ROW LEVEL SECURITY;
ALTER TABLE factory.intake_approvals FORCE ROW LEVEL SECURITY;

CREATE POLICY intake_submissions_isolated ON factory.intake_submissions
    FOR SELECT TO PUBLIC
    USING (project_id IN (
        SELECT project_id FROM factory.project_identities
        WHERE role_name = session_user
    ));
CREATE POLICY intake_submissions_insert ON factory.intake_submissions
    FOR INSERT TO factory_executor_owner
    WITH CHECK (project_id IN (
        SELECT project_id FROM factory.project_identities
        WHERE role_name = session_user AND identity_kind = 'runtime'
    ));
CREATE POLICY intake_approvals_isolated ON factory.intake_approvals
    FOR SELECT TO PUBLIC
    USING (project_id IN (
        SELECT project_id FROM factory.project_identities
        WHERE role_name = session_user
    ));
CREATE POLICY intake_approvals_insert ON factory.intake_approvals
    FOR INSERT TO factory_executor_owner
    WITH CHECK (project_id IN (
        SELECT project_id FROM factory.project_identities
        WHERE role_name = session_user AND identity_kind = 'approval'
    ));

GRANT SELECT ON factory.intake_submissions, factory.intake_approvals
    TO factory_runtime, factory_approval_authority;
GRANT SELECT, INSERT ON factory.intake_submissions, factory.intake_approvals
    TO factory_executor_owner;

-- This function registers the exact package in the same transaction as its
-- dossier, mission and plan snapshots. Its project comes from session_user.
CREATE FUNCTION factory.record_product_intake(
    p_dossier_version_no INTEGER,
    p_mission_id TEXT,
    p_mission_version_no INTEGER,
    p_plan_version_no INTEGER,
    p_idempotency_key TEXT
)
RETURNS UUID
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, factory, pg_temp
AS $record_product_intake$
DECLARE
    v_project_id UUID;
    v_dossier JSONB;
    v_mission JSONB;
    v_plan JSONB;
    v_existing factory.intake_submissions%ROWTYPE;
    v_intake_id UUID;
BEGIN
    IF p_dossier_version_no IS NULL OR p_dossier_version_no < 1
       OR p_mission_id IS NULL OR length(trim(p_mission_id)) NOT BETWEEN 1 AND 80
       OR p_mission_version_no IS NULL OR p_mission_version_no < 1
       OR p_plan_version_no IS NULL OR p_plan_version_no < 1
       OR p_idempotency_key IS NULL
       OR length(trim(p_idempotency_key)) NOT BETWEEN 1 AND 255 THEN
        RAISE EXCEPTION 'invalid product intake registration arguments';
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
        pg_catalog.hashtextextended(v_project_id::text || ':intake:' || p_idempotency_key, 0)
    );

    SELECT * INTO v_existing
    FROM factory.intake_submissions
    WHERE project_id = v_project_id AND idempotency_key = p_idempotency_key;
    IF FOUND THEN
        IF v_existing.dossier_version_no = p_dossier_version_no
           AND v_existing.mission_id = p_mission_id
           AND v_existing.mission_version_no = p_mission_version_no
           AND v_existing.plan_version_no = p_plan_version_no THEN
            RETURN v_existing.intake_id;
        END IF;
        RAISE EXCEPTION 'product intake idempotency key reused with different snapshot set';
    END IF;

    SELECT dossier INTO v_dossier
    FROM factory.product_dossier_versions
    WHERE project_id = v_project_id AND version_no = p_dossier_version_no;
    SELECT mission INTO v_mission
    FROM factory.mission_versions
    WHERE project_id = v_project_id
      AND mission_id = p_mission_id AND version_no = p_mission_version_no;
    SELECT task_plan INTO v_plan
    FROM factory.task_plan_versions
    WHERE project_id = v_project_id
      AND mission_id = p_mission_id
      AND mission_version_no = p_mission_version_no
      AND plan_version_no = p_plan_version_no;

    IF v_dossier IS NULL OR v_mission IS NULL OR v_plan IS NULL THEN
        RAISE EXCEPTION 'intake snapshot set not found for this product runtime';
    END IF;
    IF v_dossier->'lifecycle'->>'state' IS DISTINCT FROM 'pending_approval'
       OR v_mission->>'mission_id' IS DISTINCT FROM p_mission_id
       OR v_mission->>'approval_required' IS DISTINCT FROM 'true'
       OR v_plan->>'mission_id' IS DISTINCT FROM p_mission_id
       OR (v_plan->>'mission_version')::integer IS DISTINCT FROM p_mission_version_no THEN
        RAISE EXCEPTION 'snapshot set is not a pending approval-gated intake';
    END IF;

    INSERT INTO factory.intake_submissions (
        project_id, idempotency_key, dossier_version_no,
        mission_id, mission_version_no, plan_version_no, created_by_login
    ) VALUES (
        v_project_id, p_idempotency_key, p_dossier_version_no,
        p_mission_id, p_mission_version_no, p_plan_version_no, session_user
    ) RETURNING intake_id INTO v_intake_id;

    RETURN v_intake_id;
END;
$record_product_intake$;

CREATE FUNCTION factory.record_intake_approval(
    p_intake_id UUID,
    p_decision TEXT,
    p_rationale TEXT,
    p_idempotency_key TEXT
)
RETURNS UUID
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, factory, pg_temp
AS $record_intake_approval$
DECLARE
    v_project_id UUID;
    v_intake factory.intake_submissions%ROWTYPE;
    v_existing factory.intake_approvals%ROWTYPE;
    v_approval_id UUID;
BEGIN
    IF p_intake_id IS NULL
       OR p_decision IS NULL OR p_decision NOT IN ('approved', 'rejected')
       OR p_rationale IS NULL OR length(trim(p_rationale)) NOT BETWEEN 1 AND 4000
       OR p_idempotency_key IS NULL
       OR length(trim(p_idempotency_key)) NOT BETWEEN 1 AND 255 THEN
        RAISE EXCEPTION 'invalid intake approval arguments';
    END IF;

    -- The database login is the approver identity. No caller-supplied actor is accepted.
    IF NOT pg_catalog.pg_has_role(session_user, 'factory_approval_authority', 'MEMBER')
       OR pg_catalog.pg_has_role(session_user, 'factory_runtime', 'MEMBER')
       OR pg_catalog.pg_has_role(session_user, 'factory_executor_owner', 'MEMBER') THEN
        RAISE EXCEPTION 'session identity is not an isolated product approval identity';
    END IF;

    SELECT project_id INTO v_project_id
    FROM factory.project_identities
    WHERE role_name = session_user AND identity_kind = 'approval';
    IF NOT FOUND THEN
        RAISE EXCEPTION 'approval identity has no product mapping';
    END IF;

    PERFORM pg_catalog.pg_advisory_xact_lock(
        pg_catalog.hashtextextended(v_project_id::text || ':intake-approval:' || p_intake_id::text, 0)
    );

    SELECT * INTO v_intake
    FROM factory.intake_submissions
    WHERE project_id = v_project_id AND intake_id = p_intake_id;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'intake submission not found for this approval identity';
    END IF;

    SELECT * INTO v_existing
    FROM factory.intake_approvals
    WHERE project_id = v_project_id AND idempotency_key = p_idempotency_key;
    IF FOUND THEN
        IF v_existing.intake_id = p_intake_id
           AND v_existing.decision = p_decision
           AND v_existing.rationale = p_rationale
           AND v_existing.decided_by_login = session_user THEN
            RETURN v_existing.approval_id;
        END IF;
        RAISE EXCEPTION 'intake approval idempotency key reused with different intent';
    END IF;

    IF EXISTS (
        SELECT 1 FROM factory.intake_approvals
        WHERE project_id = v_project_id AND intake_id = p_intake_id
    ) THEN
        RAISE EXCEPTION 'this intake submission already has a final decision';
    END IF;

    INSERT INTO factory.intake_approvals (
        project_id, intake_id, decision, rationale,
        idempotency_key, decided_by_login
    ) VALUES (
        v_project_id, p_intake_id, p_decision, p_rationale,
        p_idempotency_key, session_user
    ) RETURNING approval_id INTO v_approval_id;

    RETURN v_approval_id;
END;
$record_intake_approval$;

-- The migration identity owns the schema; grant CREATE only for ownership transfer.
GRANT CREATE ON SCHEMA factory TO factory_executor_owner;

REVOKE ALL ON FUNCTION factory.record_product_intake(INTEGER, TEXT, INTEGER, INTEGER, TEXT) FROM PUBLIC;
REVOKE ALL ON FUNCTION factory.record_product_intake(INTEGER, TEXT, INTEGER, INTEGER, TEXT) FROM factory_approval_authority;
GRANT EXECUTE ON FUNCTION factory.record_product_intake(INTEGER, TEXT, INTEGER, INTEGER, TEXT) TO factory_runtime;
ALTER FUNCTION factory.record_product_intake(INTEGER, TEXT, INTEGER, INTEGER, TEXT) OWNER TO factory_executor_owner;

REVOKE ALL ON FUNCTION factory.record_intake_approval(UUID, TEXT, TEXT, TEXT) FROM PUBLIC;
REVOKE ALL ON FUNCTION factory.record_intake_approval(UUID, TEXT, TEXT, TEXT) FROM factory_runtime;
GRANT EXECUTE ON FUNCTION factory.record_intake_approval(UUID, TEXT, TEXT, TEXT) TO factory_approval_authority;
ALTER FUNCTION factory.record_intake_approval(UUID, TEXT, TEXT, TEXT) OWNER TO factory_executor_owner;

REVOKE CREATE ON SCHEMA factory FROM factory_executor_owner;
COMMIT;
