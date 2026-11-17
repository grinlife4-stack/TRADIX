-- DRAFT ONLY — one-time role bootstrap; do not run against Production without approval.
-- Roles are cluster-level PostgreSQL objects. Run as a trusted Neon/PostgreSQL
-- administrator with CREATEROLE, separately from ordinary schema migrations.
BEGIN;

DO $roles$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'factory_executor_owner'
    ) THEN
        EXECUTE 'CREATE ROLE factory_executor_owner NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS';
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'factory_runtime'
    ) THEN
        EXECUTE 'CREATE ROLE factory_runtime NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS';
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'factory_approval_authority'
    ) THEN
        EXECUTE 'CREATE ROLE factory_approval_authority NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS';
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'factory_identity_admin'
    ) THEN
        EXECUTE 'CREATE ROLE factory_identity_admin NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS';
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'factory_onboarding_authority'
    ) THEN
        EXECUTE 'CREATE ROLE factory_onboarding_authority NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS';
    END IF;
END
$roles$;

DO $validate$
BEGIN
    IF (
        SELECT count(*)
        FROM pg_catalog.pg_roles
        WHERE rolname IN ('factory_executor_owner', 'factory_runtime', 'factory_approval_authority', 'factory_identity_admin', 'factory_onboarding_authority')
          AND (
              rolcanlogin OR rolinherit OR rolsuper OR rolcreatedb
              OR rolcreaterole OR rolbypassrls
          )
    ) <> 0 THEN
        RAISE EXCEPTION 'factory roles exist with unsafe role attributes';
    END IF;

    IF (
        SELECT count(*)
        FROM pg_catalog.pg_roles
        WHERE rolname IN ('factory_executor_owner', 'factory_runtime', 'factory_approval_authority', 'factory_identity_admin', 'factory_onboarding_authority')
    ) <> 5 THEN
        RAISE EXCEPTION 'factory role bootstrap incomplete';
    END IF;
END
$validate$;

COMMIT;
