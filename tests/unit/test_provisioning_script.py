"""Static verification tests for database role provisioning order and migration privilege integrity."""
import os
from pathlib import Path


def test_init_db_roles_provisioning_order():
    """Verifies that init_db_roles.sql creates roles, database, and connects in valid order."""
    script_path = Path(__file__).resolve().parent.parent.parent / "scripts" / "init_db_roles.sql"
    assert script_path.exists(), f"File {script_path} does not exist."

    content = script_path.read_text(encoding="utf-8")

    # 1. Roles created first
    migrator_idx = content.find("rolname = 'regulens_migrator'")
    app_idx = content.find("rolname = 'regulens_app'")
    assert migrator_idx != -1, "regulens_migrator role creation block missing."
    assert app_idx != -1, "regulens_app role creation block missing."

    # 2. Database creation appears before connection
    create_db_idx = content.find("CREATE DATABASE regulens_dev WITH OWNER regulens_migrator")
    connect_cmd_idx = content.find(r"\c regulens_dev")
    grant_connect_idx = content.find("GRANT CONNECT ON DATABASE regulens_dev")

    assert create_db_idx != -1, "CREATE DATABASE regulens_dev statement missing."
    assert connect_cmd_idx != -1, r"\c regulens_dev statement missing."
    assert grant_connect_idx != -1, "GRANT CONNECT ON DATABASE regulens_dev statement missing."

    # Order verification: Roles -> Create DB -> Grant Connect -> Connect (\c)
    assert migrator_idx < create_db_idx, "Roles must be created before database creation."
    assert create_db_idx < grant_connect_idx, "Database must be created before granting connect privileges."
    assert grant_connect_idx < connect_cmd_idx, r"Connect privileges must be granted before \c regulens_dev."

    # 3. No premature reference to non-existent audit_logs table
    assert "REVOKE UPDATE, DELETE, TRUNCATE ON TABLE audit_logs" not in content, (
        "scripts/init_db_roles.sql must not attempt to revoke privileges on table audit_logs "
        "before migrations have created it."
    )

    # 4. Default privileges apply to objects created by regulens_migrator
    assert "ALTER DEFAULT PRIVILEGES FOR ROLE regulens_migrator IN SCHEMA public" in content


def test_migration_audit_logs_revocation_order():
    """Verifies that Alembic migration explicitly revokes UPDATE/DELETE on audit_logs after creation."""
    migration_path = (
        Path(__file__).resolve().parent.parent.parent
        / "apps"
        / "api"
        / "alembic"
        / "versions"
        / "0001_initial_schema.py"
    )
    assert migration_path.exists(), f"File {migration_path} does not exist."

    content = migration_path.read_text(encoding="utf-8")

    create_table_idx = content.find('op.create_table(\n        "audit_logs"')
    if create_table_idx == -1:
        create_table_idx = content.find('op.create_table(\r\n        "audit_logs"')
    assert create_table_idx != -1, 'Table creation for "audit_logs" missing.'

    revoke_idx = content.find("REVOKE UPDATE, DELETE, TRUNCATE ON TABLE audit_logs FROM regulens_app;")
    assert revoke_idx != -1, "Explicit REVOKE on audit_logs from regulens_app missing in migration."

    # Verify that REVOKE happens AFTER table creation
    assert create_table_idx < revoke_idx, "REVOKE on audit_logs must execute after table creation."

    # Verify append-only RLS policies exist
    assert "CREATE POLICY rls_audit_logs_select ON audit_logs" in content
    assert "CREATE POLICY rls_audit_logs_insert ON audit_logs" in content

    # Verify no UPDATE or DELETE RLS policies exist for audit_logs
    assert "CREATE POLICY rls_audit_logs_update ON audit_logs" not in content
    assert "CREATE POLICY rls_audit_logs_delete ON audit_logs" not in content
