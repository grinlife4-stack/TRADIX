-- DRAFT OPERATIONS SCRIPT. Connect as the trusted provisioner LOGIN.
-- Required psql variables:
--   project_key, display_name, product_type, repository_full_name,
--   runtime_login, approval_login
-- Set repository_full_name to an empty string for products without a Git repository.
\set ON_ERROR_STOP on

BEGIN;
SET ROLE factory_identity_admin;

DO $preflight$
BEGIN
  IF current_user <> 'factory_identity_admin'
     OR NOT pg_catalog.pg_has_role(session_user, 'factory_identity_admin', 'SET')
     OR pg_catalog.pg_has_role(session_user, 'factory_runtime', 'MEMBER')
     OR pg_catalog.pg_has_role(session_user, 'factory_approval_authority', 'MEMBER')
     OR pg_catalog.pg_has_role(session_user, 'factory_executor_owner', 'MEMBER') THEN
    RAISE EXCEPTION 'session is not an isolated factory identity provisioner';
  END IF;
END
$preflight$;

-- Registry row and both identity mappings commit or roll back together.
INSERT INTO factory.projects (
  project_key, display_name, product_type, repository_full_name
) VALUES (
  :'project_key',
  :'display_name',
  :'product_type',
  NULLIF(:'repository_full_name', '')
)
RETURNING project_id \gset

INSERT INTO factory.project_identities (role_name, project_id, identity_kind)
VALUES
  (:'runtime_login', :'project_id', 'runtime'),
  (:'approval_login', :'project_id', 'approval');

COMMIT;
RESET ROLE;

\echo Product registered with project_id=:project_id
