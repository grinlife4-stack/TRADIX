-- DRAFT ONLY — CI applies this to disposable PostgreSQL 17.
-- Records a human approval decision against one exact immutable intake snapshot set.
-- It does not create tasks, dispatch work, reserve resources, or authorize execution.
BEGIN;

-- The plan version must be tied to the exact mission version it describes.
ALTER TABLE factory.task_plan_versions
    ADD CONSTRAINT task_plan_versions_snapshot_identity_key
    UNIQUE (project_id, mission_id, mission_version_no, plan_version_no);

CREATE TABLE factory.intake_approvals (
    approval_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES factory.projects(project_id) ON DELETE RESTRICT,
    mission_id TEXT NOT NULL CHECK (length(trim(mission_id)) BETWEEN 1 AND 80),
    dossier_version_no INTEGER NOT NULL CHECK (dossier_version_no > 0),
    mission_version_no INTEGER NOT NULL CHECK (mission_version_no > 0),
    plan_version_no INTEGER NOT NULL CHECK (plan_version_no > 0),
    decision TEXT NOT NULL CHECK (decision IN ('approved', 'rejected')),
    rationale TEXT NOT NULL CHECK (length(trim(rationale)) BETWEEN 1 AND 4000),
    idempotency_key TEXT NOT NULL CHECK (length(trim(idempotency_key)) BETWEEN 1 AND 255),
    decided_by_login NAME NOT NULL,
    decided_at TIMESTAMPTZ NOT NULL DEFAULT now(),

    UNIQUE (project_id, idempotency_key),
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

CREATE INDEX intake_approvals_snapshot_idx
    ON factory.intake_approvals (
        project_id, mission_id, mission_version_no DESC, plan_version_no DESC
    );

CREATE TRIGGER intake_approvals_append_only
    BEFORE UPDATE OR DELETE ON factory.intake_approvals
    FOR EACH ROW EXECUTE FUNCTION factory.reject_mission_plan_mutation();
CREATE TRIGGER intake_approvals_no_truncate
    BEFORE TRUNCATE ON factory.intake_approvals
    FOR EACH STATEMENT EXECUTE FUNCTION factory.reject_mission_plan_mutation();

REVOKE ALL ON factory.intake_approvals FROM PUBLIC;
REVOKE UPDATE, DELETE, TRUNCATE ON factory.intake_approvals FROM factory_runtime;
REVOKE INSERT, UPDATE, DELETE, TRUNCATE ON factory.intake_approvals
    FROM factory_approval_authority;

ALTER TABLE factory.intake_approvals ENABLE ROW LEVEL SECURITY;
ALTER TABLE factory.intake_approvals FORCE ROW LEVEL SECURITY;

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

GRANT SELECT ON factory.intake_approvals
    TO factory_runtime, factory_approval_authority;
GRANT SELECT, INSERT ON factory.intake_approvals TO factory_executor_owner;

CREATE FUNCTION factory.record_intake_approval(
    p_mission_id TEXT,
    p_dossier_version_no INTEGER,
    p_mission_version_no INTEGER,
    p_plan_version_no INTEGER,
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
    v_dossier JSONB;
    v_mission JSONB;
    v_plan JSONB;
    v_existing factory.intake_approvals%ROWTYPE;
    v_approval_id UUID;
BEGIN
    IF p_mission_id IS NULL OR length(trim(p_mission_id)) NOT BETWEEN 1 AND 80
       OR p_dossier_version_no IS NULL OR p_dossier_version_no < 1
       OR p_mission_version_no IS NULL OR p_mission_version_no < 1
       OR p_plan_version_no IS NULL OR p_plan_version_no < 1
       OR p_decision IS NULL OR p_decision NOT IN ('approved', 'rejected')
       OR p_rationale IS NULL OR length(trim(p_rationale)) NOT BETWEEN 1 AND 4000
       OR p_idempotency_key IS NULL
       OR length(trim(p_idempotency_key)) NOT BETWEEN 1 AND 255 THEN
        RAISE EXCEPTION 'invalid intake approval arguments';
    END IF;

    -- The database login, not a caller-supplied actor field, is the approver identity.
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
        pg_catalog.hashtextextended(
            v_project_id::text || ':intake-approval:' || p_mission_id || ':' ||
            p_dossier_version_no::text || ':' || p_mission_version_no::text || ':' ||
            p_plan_version_no::text,
            0
        )
    );

    SELECT dossier INTO v_dossier
    FROM factory.product_dossier_versions
    WHERE project_id = v_project_id AND version_no = p_dossier_version_no;

    SELECT mission INTO v_mission
    FROM factory.mission_versions
    WHERE project_id = v_project_id
      AND mission_id = p_mission_id
      AND version_no = p_mission_version_no;

    SELECT task_plan INTO v_plan
    FROM factory.task_plan_versions
    WHERE project_id = v_project_id
      AND mission_id = p_mission_id
      AND mission_version_no = p_mission_version_no
      AND plan_version_no = p_plan_version_no;

    IF v_dossier IS NULL OR v_mission IS NULL OR v_plan IS NULL THEN
        RAISE EXCEPTION 'intake snapshot set not found for this approval identity';
    END IF;

    IF v_dossier->'lifecycle'->>'state' IS DISTINCT FROM 'pending_approval'
       OR v_mission->>'mission_id' IS DISTINCT FROM p_mission_id
       OR v_mission->>'approval_required' IS DISTINCT FROM 'true'
       OR v_plan->>'mission_id' IS DISTINCT FROM p_mission_id
       OR (v_plan->>'mission_version')::integer IS DISTINCT FROM p_mission_version_no THEN
        RAISE EXCEPTION 'snapshot set is not an approval-gated intake';
    END IF;

    SELECT * INTO v_existing
    FROM factory.intake_approvals
    WHERE project_id = v_project_id AND idempotency_key = p_idempotency_key;

    IF FOUND THEN
        IF v_existing.mission_id = p_mission_id
           AND v_existing.dossier_version_no = p_dossier_version_no
           AND v_existing.mission_version_no = p_mission_version_no
           AND v_existing.plan_version_no = p_plan_version_no
           AND v_existing.decision = p_decision
           AND v_existing.rationale = p_rationale
           AND v_existing.decided_by_login = session_user THEN
            RETURN v_existing.approval_id;
        END IF;
        RAISE EXCEPTION 'intake approval idempotency key reused with different intent';
    END IF;

    IF EXISTS (
        SELECT 1 FROM factory.intake_approvals
        WHERE project_id = v_project_id
          AND mission_id = p_mission_id
          AND dossier_version_no = p_dossier_version_no
          AND mission_version_no = p_mission_version_no
          AND plan_version_no = p_plan_version_no
    ) THEN
        RAISE EXCEPTION 'this exact intake snapshot set already has a final decision';
    END IF;

    INSERT INTO factory.intake_approvals (
        project_id, mission_id, dossier_version_no,
        mission_version_no, plan_version_no, decision,
        rationale, idempotency_key, decided_by_login
    ) VALUES (
        v_project_id, p_mission_id, p_dossier_version_no,
        p_mission_version_no, p_plan_version_no, p_decision,
        p_rationale, p_idempotency_key, session_user
    ) RETURNING approval_id INTO v_approval_id;

    RETURN v_approval_id;
END;
$record_intake_approval$;

REVOKE ALL ON FUNCTION factory.record_intake_approval(
    TEXT, INTEGER, INTEGER, INTEGER, TEXT, TEXT, TEXT
) FROM PUBLIC;
REVOKE ALL ON FUNCTION factory.record_intake_approval(
    TEXT, INTEGER, INTEGER, INTEGER, TEXT, TEXT, TEXT
) FROM factory_runtime;
GRANT EXECUTE ON FUNCTION factory.record_intake_approval(
    TEXT, INTEGER, INTEGER, INTEGER, TEXT, TEXT, TEXT
) TO factory_approval_authority;
ALTER FUNCTION factory.record_intake_approval(
    TEXT, INTEGER, INTEGER, INTEGER, TEXT, TEXT, TEXT
) OWNER TO factory_executor_owner;

COMMIT;
