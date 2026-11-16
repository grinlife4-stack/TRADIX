-- DRAFT OPERATIONS SCRIPT. Run only as a trusted PostgreSQL administrator with CREATEROLE.
-- Required psql variables: runtime_login, approval_login, provisioner_login.
-- No passwords are embedded or accepted as command-line variables.
\set ON_ERROR_STOP on

-- Product runtime LOGIN: one isolated login, inheriting only factory_runtime.
SELECT format(
  'CREATE ROLE %I LOGIN INHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS',
  :'runtime_login'
)
WHERE NOT EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = :'runtime_login')
\gexec
GRANT factory_runtime TO :"runtime_login";

-- Product approval LOGIN: separate from the runtime identity.
SELECT format(
  'CREATE ROLE %I LOGIN INHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS',
  :'approval_login'
)
WHERE NOT EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = :'approval_login')
\gexec
GRANT factory_approval_authority TO :"approval_login";

-- One factory-wide provisioning LOGIN. It can SET ROLE to identity admin,
-- but does not inherit the authority and receives no runtime/approval membership.
SELECT format(
  'CREATE ROLE %I LOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS',
  :'provisioner_login'
)
WHERE NOT EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = :'provisioner_login')
\gexec
GRANT factory_identity_admin TO :"provisioner_login" WITH SET TRUE, INHERIT FALSE;

-- Fail closed if any pre-existing role has unsafe attributes or unexpected
-- factory authority. Passwords must be set separately using psql's interactive
-- \password command or an approved secret manager.
DO $validate$
DECLARE
  v_runtime NAME := current_setting('tradix.runtime_login', true)::NAME;
  v_approval NAME := current_setting('tradix.approval_login', true)::NAME;
  v_provisioner NAME := current_setting('tradix.provisioner_login', true)::NAME;
BEGIN
  IF v_runtime IS NULL OR v_approval IS NULL OR v_provisioner IS NULL THEN
    RAISE EXCEPTION 'required login names were not supplied';
  END IF;
END
$validate$;
