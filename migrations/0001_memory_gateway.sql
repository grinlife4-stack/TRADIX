-- Memory Gateway MVP schema
-- Apply only to an isolated development branch. PostgreSQL 15+.
BEGIN;

CREATE TABLE IF NOT EXISTS memory_projects (
  project_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  project_key text NOT NULL UNIQUE,
  name text NOT NULL,
  status text NOT NULL DEFAULT 'ACTIVE'
    CHECK (status IN ('PLANNED','ACTIVE','BLOCKED','PAUSED','COMPLETED','ARCHIVED')),
  current_state jsonb NOT NULL DEFAULT '{}'::jsonb,
  state_version bigint NOT NULL DEFAULT 1 CHECK (state_version > 0),
  current_commit text,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS memory_missions (
  mission_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id uuid NOT NULL REFERENCES memory_projects(project_id),
  mission_key text NOT NULL,
  title text NOT NULL,
  status text NOT NULL DEFAULT 'ACTIVE'
    CHECK (status IN ('DRAFT','ACTIVE','BLOCKED','PAUSED','COMPLETED','CANCELLED')),
  mission_version bigint NOT NULL DEFAULT 1 CHECK (mission_version > 0),
  objective text NOT NULL,
  constraints jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE(project_id, mission_key)
);

CREATE TABLE IF NOT EXISTS memory_decisions (
  decision_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id uuid NOT NULL REFERENCES memory_projects(project_id),
  mission_id uuid REFERENCES memory_missions(mission_id),
  title text NOT NULL,
  content jsonb NOT NULL,
  rationale text NOT NULL DEFAULT '',
  status text NOT NULL DEFAULT 'PROPOSED'
    CHECK (status IN ('PROPOSED','APPROVED','REJECTED','SUPERSEDED','REVOKED')),
  version bigint NOT NULL DEFAULT 1 CHECK (version > 0),
  proposed_by text NOT NULL,
  approved_by text,
  approved_at timestamptz,
  source_refs jsonb NOT NULL DEFAULT '[]'::jsonb
    CHECK (jsonb_typeof(source_refs) = 'array'),
  supersedes uuid REFERENCES memory_decisions(decision_id),
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  CHECK (
    (status = 'APPROVED' AND approved_by IS NOT NULL AND approved_at IS NOT NULL)
    OR status <> 'APPROVED'
  )
);

CREATE INDEX IF NOT EXISTS memory_decisions_project_status_idx
  ON memory_decisions(project_id, status, updated_at DESC);

CREATE TABLE IF NOT EXISTS memory_evidence (
  evidence_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id uuid NOT NULL REFERENCES memory_projects(project_id),
  kind text NOT NULL
    CHECK (kind IN ('COMMIT','TEST_RESULT','BUILD_LOG','DEPLOYMENT','DOCUMENT','ARTIFACT','EXTERNAL_RECORD')),
  uri text NOT NULL,
  content_hash char(64) NOT NULL CHECK (content_hash ~ '^[0-9a-fA-F]{64}$'),
  verification_status text NOT NULL DEFAULT 'UNVERIFIED'
    CHECK (verification_status IN ('UNVERIFIED','VERIFIED','REJECTED','EXPIRED')),
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_by text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS memory_evidence_project_created_idx
  ON memory_evidence(project_id, created_at DESC);

CREATE TABLE IF NOT EXISTS memory_checkpoints (
  checkpoint_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id uuid NOT NULL REFERENCES memory_projects(project_id),
  mission_id uuid REFERENCES memory_missions(mission_id),
  checkpoint_seq bigint NOT NULL CHECK (checkpoint_seq > 0),
  verified_state jsonb NOT NULL,
  source_versions jsonb NOT NULL DEFAULT '{}'::jsonb,
  active_tasks jsonb NOT NULL DEFAULT '[]'::jsonb
    CHECK (jsonb_typeof(active_tasks) = 'array'),
  approved_decisions jsonb NOT NULL DEFAULT '[]'::jsonb
    CHECK (jsonb_typeof(approved_decisions) = 'array'),
  open_issues jsonb NOT NULL DEFAULT '[]'::jsonb
    CHECK (jsonb_typeof(open_issues) = 'array'),
  pending_operations jsonb NOT NULL DEFAULT '[]'::jsonb
    CHECK (jsonb_typeof(pending_operations) = 'array'),
  next_action jsonb,
  unknowns jsonb NOT NULL DEFAULT '[]'::jsonb
    CHECK (jsonb_typeof(unknowns) = 'array'),
  conflicts jsonb NOT NULL DEFAULT '[]'::jsonb
    CHECK (jsonb_typeof(conflicts) = 'array'),
  created_by text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE(project_id, checkpoint_seq)
);

CREATE INDEX IF NOT EXISTS memory_checkpoints_latest_idx
  ON memory_checkpoints(project_id, checkpoint_seq DESC);

CREATE TABLE IF NOT EXISTS memory_events (
  event_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id uuid NOT NULL REFERENCES memory_projects(project_id),
  mission_id uuid REFERENCES memory_missions(mission_id),
  event_type text NOT NULL,
  actor_id text NOT NULL,
  correlation_id uuid,
  idempotency_key text NOT NULL,
  payload jsonb NOT NULL,
  source_versions jsonb NOT NULL DEFAULT '{}'::jsonb,
  occurred_at timestamptz NOT NULL,
  recorded_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE(project_id, idempotency_key)
);

CREATE INDEX IF NOT EXISTS memory_events_project_time_idx
  ON memory_events(project_id, recorded_at DESC);

CREATE OR REPLACE FUNCTION memory_reject_event_mutation()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION 'memory_events is append-only';
END;
$$;

DROP TRIGGER IF EXISTS memory_events_immutable ON memory_events;
CREATE TRIGGER memory_events_immutable
BEFORE UPDATE OR DELETE ON memory_events
FOR EACH ROW EXECUTE FUNCTION memory_reject_event_mutation();

CREATE OR REPLACE FUNCTION memory_set_updated_at()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS memory_projects_updated_at ON memory_projects;
CREATE TRIGGER memory_projects_updated_at
BEFORE UPDATE ON memory_projects
FOR EACH ROW EXECUTE FUNCTION memory_set_updated_at();

DROP TRIGGER IF EXISTS memory_missions_updated_at ON memory_missions;
CREATE TRIGGER memory_missions_updated_at
BEFORE UPDATE ON memory_missions
FOR EACH ROW EXECUTE FUNCTION memory_set_updated_at();

DROP TRIGGER IF EXISTS memory_decisions_updated_at ON memory_decisions;
CREATE TRIGGER memory_decisions_updated_at
BEFORE UPDATE ON memory_decisions
FOR EACH ROW EXECUTE FUNCTION memory_set_updated_at();

COMMIT;


-- Read-only bootstrap context for a fresh executive-leader session.
CREATE OR REPLACE FUNCTION memory_bootstrap_context(p_project_key text)
RETURNS jsonb
LANGUAGE sql
STABLE
AS $$
  SELECT jsonb_build_object(
    'schema_version', '1.0',
    'generated_at', now(),
    'project', jsonb_build_object(
      'project_id', p.project_id,
      'project_key', p.project_key,
      'name', p.name,
      'status', p.status,
      'state_version', p.state_version,
      'current_state', p.current_state,
      'current_commit', p.current_commit
    ),
    'active_missions', COALESCE((
      SELECT jsonb_agg(jsonb_build_object(
        'mission_id', m.mission_id,
        'mission_key', m.mission_key,
        'title', m.title,
        'status', m.status,
        'mission_version', m.mission_version,
        'objective', m.objective,
        'constraints', m.constraints
      ) ORDER BY m.updated_at DESC)
      FROM memory_missions m
      WHERE m.project_id = p.project_id AND m.status = 'ACTIVE'
    ), '[]'::jsonb),
    'approved_decisions', COALESCE((
      SELECT jsonb_agg(jsonb_build_object(
        'decision_id', d.decision_id,
        'title', d.title,
        'content', d.content,
        'rationale', d.rationale,
        'version', d.version,
        'approved_at', d.approved_at,
        'source_refs', d.source_refs
      ) ORDER BY d.approved_at DESC)
      FROM memory_decisions d
      WHERE d.project_id = p.project_id AND d.status = 'APPROVED'
    ), '[]'::jsonb),
    'latest_checkpoint', (
      SELECT jsonb_build_object(
        'checkpoint_id', c.checkpoint_id,
        'checkpoint_seq', c.checkpoint_seq,
        'verified_state', c.verified_state,
        'source_versions', c.source_versions,
        'active_tasks', c.active_tasks,
        'approved_decisions', c.approved_decisions,
        'open_issues', c.open_issues,
        'pending_operations', c.pending_operations,
        'next_action', c.next_action,
        'unknowns', c.unknowns,
        'conflicts', c.conflicts,
        'created_at', c.created_at
      )
      FROM memory_checkpoints c
      WHERE c.project_id = p.project_id
      ORDER BY c.checkpoint_seq DESC
      LIMIT 1
    ),
    'recent_events', COALESCE((
      SELECT jsonb_agg(jsonb_build_object(
        'event_id', e.event_id,
        'event_type', e.event_type,
        'actor_id', e.actor_id,
        'payload', e.payload,
        'recorded_at', e.recorded_at
      ) ORDER BY e.recorded_at DESC)
      FROM (
        SELECT * FROM memory_events
        WHERE project_id = p.project_id
        ORDER BY recorded_at DESC
        LIMIT 20
      ) e
    ), '[]'::jsonb)
  )
  FROM memory_projects p
  WHERE p.project_key = p_project_key;
$$;
