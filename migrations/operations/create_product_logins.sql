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

-- Validate that reused names do not carry extra authority or unsafe attributes.
SELECT (
  SELECT rolcanlogin AND rolinherit AND NOT rolsuper AND NOT rolcreatedb
         AND NOT rolcreaterole AND NOT rolbypassrls
  FROM pg_catalog.pg_roles WHERE rolname = :'runtime_login'
) AS runtime_ok \gset
\if :runtime_ok
\else
  \echo 'Runtime LOGIN has unsafe or missing role attributes.'
  \quit 3
\endif

SELECT (
  SELECT rolcanlogin AND rolinherit AND NOT rolsuper AND NOT rolcreatedb
         AND NOT rolcreaterole AND NOT rolbypassrls
  FROM pg_catalog.pg_roles WHERE rolname = :'approval_login'
) AS approval_ok \gset
\if :approval_ok
\else
  \echo 'Approval LOGIN has unsafe or missing role attributes.'
  \quit 3
\endif

SELECT (
  SELECT rolcanlogin AND NOT rolinherit AND NOT rolsuper AND NOT rolcreatedb
         AND NOT rolcreaterole AND NOT rolbypassrls
  FROM pg_catalog.pg_roles WHERE rolname = :'provisioner_login'
) AS provisioner_ok \gset
\if :provisioner_ok
\else
  \echo 'Provisioner LOGIN has unsafe or missing role attributes.'
  \quit 3
\endif

SELECT (
  pg_catalog.pg_has_role(:'runtime_login', 'factory_runtime', 'MEMBER')
  AND NOT EXISTS (
    SELECT 1 FROM pg_catalog.pg_auth_members m
    JOIN pg_catalog.pg_roles granted_role ON granted_role.oid = m.roleid
    WHERE pg_catalog.pg_get_userbyid(m.member) = :'runtime_login'
      AND granted_role.rolname <> 'factory_runtime'
  )
) AS runtime_membership_ok \gset
\if :runtime_membership_ok
\else
  \echo 'Runtime LOGIN has missing or unexpected role memberships.'
  \quit 3
\endif

SELECT (
  pg_catalog.pg_has_role(:'approval_login', 'factory_approval_authority', 'MEMBER')
  AND NOT EXISTS (
    SELECT 1 FROM pg_catalog.pg_auth_members m
    JOIN pg_catalog.pg_roles granted_role ON granted_role.oid = m.roleid
    WHERE pg_catalog.pg_get_userbyid(m.member) = :'approval_login'
      AND granted_role.rolname <> 'factory_approval_authority'
  )
) AS approval_membership_ok \gset
\if :approval_membership_ok
\else
  \echo 'Approval LOGIN has missing or unexpected role memberships.'
  \quit 3
\endif

SELECT (
  pg_catalog.pg_has_role(:'provisioner_login', 'factory_identity_admin', 'SET')
  AND NOT pg_catalog.pg_has_role(:'provisioner_login', 'factory_identity_admin', 'USAGE')
  AND NOT pg_catalog.pg_has_role(:'provisioner_login', 'factory_runtime', 'MEMBER')
  AND NOT pg_catalog.pg_has_role(:'provisioner_login', 'factory_approval_authority', 'MEMBER')
  AND NOT pg_catalog.pg_has_role(:'provisioner_login', 'factory_executor_owner', 'MEMBER')
) AS provisioner_membership_ok \gset
\if :provisioner_membership_ok
\else
  \echo 'Provisioner LOGIN has unsafe or unexpected role memberships.'
  \quit 3
\endif

\echo 'Product LOGIN roles and provisioner role passed preflight.'
