-- ==============================================================================
-- ReguLens SaaS: Database Role Provisioning and Privilege Separation Script
-- File: scripts/init_db_roles.sql
-- ==============================================================================
-- Purpose:
-- 1. Separates DDL schema migration privileges from runtime application privileges.
-- 2. Provisions the runtime role (regulens_app) with NOBYPASSRLS and NOSUPERUSER.
-- 3. Enforces immutable audit logging by revoking UPDATE, DELETE, and TRUNCATE.
-- 4. Establishes safe default privileges for all tables created by the migration role.
--
-- Execution Instructions:
-- Execute this script as a PostgreSQL cluster administrator (e.g., 'postgres'):
--
--   psql -U postgres -d postgres -f scripts/init_db_roles.sql
--
-- IMPORTANT SECURITY NOTICE:
-- - NEVER commit production passwords to version control.
-- - Replace placeholders 'CHANGE_MIGRATOR_PASSWORD_HERE' and 'CHANGE_APP_PASSWORD_HERE'
--   with cryptographically strong passwords or inject via environment variables before running.
-- ==============================================================================

\set ON_ERROR_STOP on

-- 1. Create Migration Role (DDL Migration Owner)
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'regulens_migrator') THEN
        CREATE ROLE regulens_migrator WITH LOGIN PASSWORD 'CHANGE_MIGRATOR_PASSWORD_HERE';
        RAISE NOTICE 'Role regulens_migrator created.';
    ELSE
        RAISE NOTICE 'Role regulens_migrator already exists.';
    END IF;
END
$$;

-- 2. Create Runtime Application Role (Unprivileged, Subject to RLS)
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'regulens_app') THEN
        CREATE ROLE regulens_app WITH LOGIN PASSWORD 'CHANGE_APP_PASSWORD_HERE';
        RAISE NOTICE 'Role regulens_app created.';
    ELSE
        RAISE NOTICE 'Role regulens_app already exists.';
    END IF;
END
$$;

-- 3. Enforce Role Attributes (Defense-in-Depth)
-- The runtime application role MUST NEVER have superuser privileges or BYPASSRLS.
ALTER ROLE regulens_app WITH 
    NOSUPERUSER 
    NOCREATEDB 
    NOCREATEROLE 
    NOINHERIT 
    NOBYPASSRLS;

-- 4. Grant Database Connect Privileges
GRANT CONNECT ON DATABASE regulens_dev TO regulens_migrator;
GRANT CONNECT ON DATABASE regulens_dev TO regulens_app;

-- Connect to target database
\c regulens_dev

-- 5. Schema Ownership & DDL Privileges
-- The migration role owns the public schema and executes Alembic migrations.
GRANT ALL ON SCHEMA public TO regulens_migrator;
ALTER SCHEMA public OWNER TO regulens_migrator;

-- 6. Runtime Role Schema Usage
-- The runtime role can execute queries within the public schema, but cannot alter schema DDL.
GRANT USAGE ON SCHEMA public TO regulens_app;

-- 7. Table Level Data Access Privileges
-- Grant standard CRUD operations to the runtime role on all current tables
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO regulens_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO regulens_app;

-- 8. Immutable Audit Log Enforcement
-- Revoke UPDATE, DELETE, and TRUNCATE on audit_logs from the runtime role.
-- Even if an attacker attempts an update via application credentials, PostgreSQL rejects it at the SQL engine layer.
REVOKE UPDATE, DELETE, TRUNCATE ON TABLE audit_logs FROM regulens_app;

-- Prevent table truncation across all tables by runtime role
REVOKE TRUNCATE ON ALL TABLES IN SCHEMA public FROM regulens_app;

-- 9. Default Privileges for Future Tables
-- When regulens_migrator creates new tables via Alembic migrations, grant CRUD to regulens_app automatically.
ALTER DEFAULT PRIVILEGES FOR ROLE regulens_migrator IN SCHEMA public 
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO regulens_app;

ALTER DEFAULT PRIVILEGES FOR ROLE regulens_migrator IN SCHEMA public 
    GRANT USAGE, SELECT ON SEQUENCES TO regulens_app;

-- Ensure audit_logs immutability is maintained if recreated
ALTER DEFAULT PRIVILEGES FOR ROLE regulens_migrator IN SCHEMA public 
    REVOKE TRUNCATE ON TABLES FROM regulens_app;

-- ==============================================================================
-- Verification Queries (Run after execution):
-- 1. Check role attributes:
--    SELECT rolname, rolsuper, rolbypassrls FROM pg_roles WHERE rolname IN ('regulens_app', 'regulens_migrator');
--    Expected: regulens_app -> rolsuper=f, rolbypassrls=f
-- 2. Check audit_logs privileges:
--    SELECT grantee, privilege_type FROM information_schema.role_table_grants WHERE table_name = 'audit_logs' AND grantee = 'regulens_app';
--    Expected: SELECT, INSERT only (NO UPDATE, NO DELETE).
-- ==============================================================================
