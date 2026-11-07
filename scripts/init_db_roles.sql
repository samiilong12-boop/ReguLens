-- ==============================================================================
-- ReguLens SaaS: Database Role Provisioning and Privilege Separation Script
-- File: scripts/init_db_roles.sql
-- ==============================================================================
-- Purpose:
-- 1. Separates DDL schema migration privileges from runtime application privileges.
-- 2. Creates the target database (regulens_dev) if absent, with owner regulens_migrator.
-- 3. Provisions the runtime role (regulens_app) with NOBYPASSRLS and NOSUPERUSER.
-- 4. Establishes safe default privileges for all tables created by the migration role.
-- 5. Defers table-level revocations (audit_logs immutability) to Alembic migration DDL.
--
-- Execution Instructions:
-- Execute this script using the PostgreSQL CLI ('psql') as a cluster superuser (e.g., 'postgres'):
--
--   psql -U postgres -d postgres -f scripts/init_db_roles.sql
--
-- REQUIRED PRIVILEGES:
-- The executing account MUST possess cluster superuser privileges (or CREATEROLE and ownership
-- of regulens_dev). Superuser privileges are required to provision login roles with specific attributes,
-- assign database ownership to regulens_migrator, and alter existing database ownership safely.
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
        CREATE ROLE regulens_migrator WITH LOGIN PASSWORD 'CHANGE_MIGRATOR_PASSWORD_HERE' CREATEDB;
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

-- 4. Conditionally Create Database 'regulens_dev' with Owner 'regulens_migrator'
-- Note: In PostgreSQL, CREATE DATABASE cannot run inside a transaction block.
-- The query below uses psql \gexec to dynamically execute CREATE DATABASE only when absent.
SELECT 'CREATE DATABASE regulens_dev WITH OWNER regulens_migrator'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'regulens_dev')\gexec

-- 4b. Reassign Database Ownership to 'regulens_migrator' If Owned by Another Role
-- If regulens_dev already existed with an owner other than regulens_migrator (e.g. postgres),
-- dynamically execute ALTER DATABASE outside of a transaction block using \gexec.
-- Note: In PostgreSQL, ALTER DATABASE cannot run inside a transaction block.
SELECT 'ALTER DATABASE regulens_dev OWNER TO regulens_migrator'
FROM pg_database d
JOIN pg_roles r ON d.datdba = r.oid
WHERE d.datname = 'regulens_dev' AND r.rolname <> 'regulens_migrator'\gexec

-- 4c. Verify Database Ownership (Catalog Assertion)
-- Enforces that regulens_dev is strictly owned by regulens_migrator.
-- If ownership is incorrect (e.g. if ALTER DATABASE was skipped or failed due to insufficient privileges),
-- abort execution immediately with a clear error and required remediation instructions.
DO $$
DECLARE
    actual_owner text;
    executing_user text;
BEGIN
    SELECT r.rolname INTO actual_owner
    FROM pg_database d
    JOIN pg_roles r ON d.datdba = r.oid
    WHERE d.datname = 'regulens_dev';

    IF actual_owner IS NULL THEN
        RAISE EXCEPTION 'Database regulens_dev does not exist after creation step.';
    END IF;

    IF actual_owner <> 'regulens_migrator' THEN
        SELECT current_user INTO executing_user;
        RAISE EXCEPTION 'Security error: Database regulens_dev is owned by ''%'' instead of expected owner ''regulens_migrator''. Current executing user is ''%''. Reassigning database ownership requires cluster superuser privileges. Remediation: Run as superuser: ALTER DATABASE regulens_dev OWNER TO regulens_migrator;',
            actual_owner, executing_user;
    ELSE
        RAISE NOTICE 'Database regulens_dev ownership verified: regulens_migrator.';
    END IF;
END
$$;

-- 5. Grant Database Connect Privileges
GRANT CONNECT ON DATABASE regulens_dev TO regulens_migrator;
GRANT CONNECT ON DATABASE regulens_dev TO regulens_app;

-- 6. Connect to Target Database
\c regulens_dev

-- 7. Schema Ownership & DDL Privileges
-- The migration role owns the public schema and executes Alembic migrations.
GRANT ALL ON SCHEMA public TO regulens_migrator;
ALTER SCHEMA public OWNER TO regulens_migrator;

-- 8. Runtime Role Schema Usage
-- The runtime role can execute queries within the public schema, but cannot alter schema DDL.
GRANT USAGE ON SCHEMA public TO regulens_app;

-- 9. Default Privileges for Future Tables Created by regulens_migrator
-- When regulens_migrator creates new tables via Alembic migrations, grant DML to regulens_app automatically.
ALTER DEFAULT PRIVILEGES FOR ROLE regulens_migrator IN SCHEMA public 
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO regulens_app;

ALTER DEFAULT PRIVILEGES FOR ROLE regulens_migrator IN SCHEMA public 
    GRANT USAGE, SELECT ON SEQUENCES TO regulens_app;

-- Prevent table truncation across all future tables by runtime role
ALTER DEFAULT PRIVILEGES FOR ROLE regulens_migrator IN SCHEMA public 
    REVOKE TRUNCATE ON TABLES FROM regulens_app;

-- ==============================================================================
-- NOTE ON AUDIT_LOGS IMMUTABILITY:
-- Tables do not exist at role provisioning time. Table creation is performed by
-- Alembic migrations (alembic upgrade head).
--
-- To prevent default privilege leakage (ALTER DEFAULT PRIVILEGES granting UPDATE/DELETE),
-- the Alembic migration (0001_initial_schema.py) explicitly executes revocation of
-- UPDATE, DELETE, and TRUNCATE privileges on audit_logs from regulens_app
-- immediately after audit_logs is created, backed by append-only RLS policies.
-- ==============================================================================
