-- Project-scoped read credentials and least-privilege Memory Gateway runtime.
-- Apply only after 0001_memory_gateway.sql, on an isolated/approved database.
BEGIN;

DO $roles$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname='memory_gateway_owner') THEN
    CREATE ROLE memory_gateway_owner NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname='memory_gateway_runtime') THEN
    CREATE ROLE memory_gateway_runtime NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS;
  END IF;
END
$roles$;

CREATE TABLE IF NOT EXISTS public.memory_gateway_tokens (
  token_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id uuid NOT NULL REFERENCES public.memory_projects(project_id) ON DELETE CASCADE,
  token_hash bytea NOT NULL UNIQUE CHECK (octet_length(token_hash)=32),
  created_at timestamptz NOT NULL DEFAULT now(),
  expires_at timestamptz,
  revoked_at timestamptz
);
CREATE INDEX IF NOT EXISTS memory_gateway_tokens_project_idx
  ON public.memory_gateway_tokens(project_id) WHERE revoked_at IS NULL;

GRANT USAGE ON SCHEMA public TO memory_gateway_owner, memory_gateway_runtime;
GRANT SELECT ON public.memory_projects, public.memory_missions, public.memory_decisions,
  public.memory_evidence, public.memory_checkpoints, public.memory_events,
  public.memory_gateway_tokens TO memory_gateway_owner;

ALTER TABLE public.memory_projects ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.memory_projects FORCE ROW LEVEL SECURITY;
ALTER TABLE public.memory_missions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.memory_missions FORCE ROW LEVEL SECURITY;
ALTER TABLE public.memory_decisions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.memory_decisions FORCE ROW LEVEL SECURITY;
ALTER TABLE public.memory_evidence ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.memory_evidence FORCE ROW LEVEL SECURITY;
ALTER TABLE public.memory_checkpoints ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.memory_checkpoints FORCE ROW LEVEL SECURITY;
ALTER TABLE public.memory_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.memory_events FORCE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS memory_gateway_project_scope ON public.memory_projects;
CREATE POLICY memory_gateway_project_scope ON public.memory_projects
  FOR SELECT TO memory_gateway_owner
  USING (project_id = NULLIF(current_setting('tradix.project_id', true),'')::uuid);
DROP POLICY IF EXISTS memory_gateway_project_scope ON public.memory_missions;
CREATE POLICY memory_gateway_project_scope ON public.memory_missions
  FOR SELECT TO memory_gateway_owner
  USING (project_id = NULLIF(current_setting('tradix.project_id', true),'')::uuid);
DROP POLICY IF EXISTS memory_gateway_project_scope ON public.memory_decisions;
CREATE POLICY memory_gateway_project_scope ON public.memory_decisions
  FOR SELECT TO memory_gateway_owner
  USING (project_id = NULLIF(current_setting('tradix.project_id', true),'')::uuid);
DROP POLICY IF EXISTS memory_gateway_project_scope ON public.memory_evidence;
CREATE POLICY memory_gateway_project_scope ON public.memory_evidence
  FOR SELECT TO memory_gateway_owner
  USING (project_id = NULLIF(current_setting('tradix.project_id', true),'')::uuid);
DROP POLICY IF EXISTS memory_gateway_project_scope ON public.memory_checkpoints;
CREATE POLICY memory_gateway_project_scope ON public.memory_checkpoints
  FOR SELECT TO memory_gateway_owner
  USING (project_id = NULLIF(current_setting('tradix.project_id', true),'')::uuid);
DROP POLICY IF EXISTS memory_gateway_project_scope ON public.memory_events;
CREATE POLICY memory_gateway_project_scope ON public.memory_events
  FOR SELECT TO memory_gateway_owner
  USING (project_id = NULLIF(current_setting('tradix.project_id', true),'')::uuid);

REVOKE ALL ON public.memory_projects, public.memory_missions, public.memory_decisions,
  public.memory_evidence, public.memory_checkpoints, public.memory_events,
  public.memory_gateway_tokens FROM PUBLIC, memory_gateway_runtime;
REVOKE ALL ON FUNCTION public.memory_bootstrap_context(text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.memory_bootstrap_context(text) TO memory_gateway_owner;

CREATE OR REPLACE FUNCTION public.memory_bootstrap_context_for_token(p_token_hash bytea)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, public
AS $function$
DECLARE
  v_project_id uuid;
  v_project_key text;
  v_context jsonb;
BEGIN
  IF p_token_hash IS NULL OR octet_length(p_token_hash) <> 32 THEN
    RETURN NULL;
  END IF;

  SELECT t.project_id, p.project_key
    INTO v_project_id, v_project_key
    FROM public.memory_gateway_tokens t
    JOIN public.memory_projects p ON p.project_id=t.project_id
   WHERE t.token_hash=p_token_hash
     AND t.revoked_at IS NULL
     AND (t.expires_at IS NULL OR t.expires_at > now());

  IF NOT FOUND THEN
    RETURN NULL;
  END IF;

  PERFORM set_config('tradix.project_id', v_project_id::text, true);
  v_context := public.memory_bootstrap_context(v_project_key);
  RETURN v_context;
END;
$function$;

ALTER FUNCTION public.memory_bootstrap_context_for_token(bytea) OWNER TO memory_gateway_owner;
REVOKE ALL ON FUNCTION public.memory_bootstrap_context_for_token(bytea) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.memory_bootstrap_context_for_token(bytea) TO memory_gateway_runtime;

ALTER ROLE memory_gateway_runtime SET statement_timeout='10s';
ALTER ROLE memory_gateway_runtime SET idle_in_transaction_session_timeout='15s';

COMMIT;
