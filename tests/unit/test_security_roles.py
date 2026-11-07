"""Unit tests for runtime database role verification and privilege enforcement."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.db.session import verify_database_role, DatabaseSecurityError
from app.main import lifespan


@pytest.mark.asyncio
async def test_runtime_role_accepted_when_unprivileged():
    """Runtime role 'regulens_app' with no superuser and no bypassrls is accepted."""
    mock_session = AsyncMock()
    mock_result = MagicMock()
    # (rolname, rolsuper, rolbypassrls)
    mock_result.first.return_value = ("regulens_app", False, False)
    mock_session.execute.return_value = mock_result

    role = await verify_database_role(mock_session)
    assert role == "regulens_app"


@pytest.mark.asyncio
async def test_privileged_role_postgres_rejected():
    """Privileged cluster administrator 'postgres' must be rejected immediately."""
    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.first.return_value = ("postgres", True, True)
    mock_session.execute.return_value = mock_result

    with pytest.raises(RuntimeError) as excinfo:
        await verify_database_role(mock_session)
    err = str(excinfo.value)
    assert "Security violation" in err
    assert "privileged database role 'postgres'" in err


@pytest.mark.asyncio
async def test_privileged_role_regulens_migrator_rejected():
    """Schema owner role 'regulens_migrator' must be rejected for runtime connection."""
    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.first.return_value = ("regulens_migrator", False, False)
    mock_session.execute.return_value = mock_result

    with pytest.raises(RuntimeError) as excinfo:
        await verify_database_role(mock_session)
    err = str(excinfo.value)
    assert "Security violation" in err
    assert "privileged database role 'regulens_migrator'" in err


@pytest.mark.asyncio
async def test_role_with_superuser_rejected():
    """Any role with superuser privileges must be rejected."""
    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.first.return_value = ("regulens_app", True, False)
    mock_session.execute.return_value = mock_result

    with pytest.raises(RuntimeError) as excinfo:
        await verify_database_role(mock_session)
    assert "has superuser privileges" in str(excinfo.value)


@pytest.mark.asyncio
async def test_role_with_bypassrls_rejected():
    """Any role with BYPASSRLS must be rejected."""
    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.first.return_value = ("regulens_app", False, True)
    mock_session.execute.return_value = mock_result

    with pytest.raises(RuntimeError) as excinfo:
        await verify_database_role(mock_session)
    assert "has BYPASSRLS privilege" in str(excinfo.value)


@pytest.mark.asyncio
async def test_unexpected_role_name_rejected():
    """Any role name other than expected 'regulens_app' is rejected."""
    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.first.return_value = ("unauthorized_user", False, False)
    mock_session.execute.return_value = mock_result

    with pytest.raises(RuntimeError) as excinfo:
        await verify_database_role(mock_session)
    assert "does not match expected runtime role 'regulens_app'" in str(excinfo.value)


@pytest.mark.asyncio
async def test_verification_does_not_leak_passwords():
    """Verification exceptions must never print connection passwords."""
    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.first.return_value = ("postgres", True, True)
    mock_session.execute.return_value = mock_result

    with pytest.raises(RuntimeError) as excinfo:
        await verify_database_role(mock_session)
    err = str(excinfo.value)
    assert "password" not in err.lower()


@pytest.mark.asyncio
async def test_missing_role_query_row_raises_database_security_error():
    """If pg_roles query returns no row, DatabaseSecurityError must be raised."""
    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.first.return_value = None
    mock_session.execute.return_value = mock_result

    with pytest.raises(DatabaseSecurityError) as excinfo:
        await verify_database_role(mock_session)
    assert "Unable to query pg_roles for current_user" in str(excinfo.value)


@pytest.mark.asyncio
async def test_lifespan_aborts_on_database_security_error_in_development(monkeypatch):
    """When DB is connected but role verification fails, lifespan must abort even in development."""
    mock_session = AsyncMock()

    @asynccontextmanager
    async def mock_session_maker():
        yield mock_session

    monkeypatch.setattr("app.core.config.settings.CHECK_DB_ROLE_ON_STARTUP", True)
    monkeypatch.setattr("app.core.config.settings.ENVIRONMENT", "development")

    with patch("app.db.session.async_session_maker", mock_session_maker), \
         patch("app.db.session.verify_database_role", side_effect=DatabaseSecurityError("Role verification failed")):
        test_app = FastAPI()
        with pytest.raises(DatabaseSecurityError):
            async with lifespan(test_app):
                pass


@pytest.mark.asyncio
async def test_lifespan_aborts_on_verification_query_error(monkeypatch):
    """When DB is connected but verification query raises an error, lifespan aborts with DatabaseSecurityError."""
    mock_session = AsyncMock()

    @asynccontextmanager
    async def mock_session_maker():
        yield mock_session

    monkeypatch.setattr("app.core.config.settings.CHECK_DB_ROLE_ON_STARTUP", True)
    monkeypatch.setattr("app.core.config.settings.ENVIRONMENT", "development")

    with patch("app.db.session.async_session_maker", mock_session_maker), \
         patch("app.db.session.verify_database_role", side_effect=Exception("Catalog access error")):
        test_app = FastAPI()
        with pytest.raises(DatabaseSecurityError) as excinfo:
            async with lifespan(test_app):
                pass
        assert "Database is reachable but role verification query failed" in str(excinfo.value)


@pytest.mark.asyncio
async def test_lifespan_aborts_on_unreachable_db_in_production(monkeypatch):
    """In production, an unreachable database during startup must fail closed with RuntimeError."""
    @asynccontextmanager
    async def mock_failing_session_maker():
        raise ConnectionRefusedError("Database connection refused")
        yield  # noqa

    monkeypatch.setattr("app.core.config.settings.CHECK_DB_ROLE_ON_STARTUP", True)
    monkeypatch.setattr("app.core.config.settings.ENVIRONMENT", "production")

    with patch("app.db.session.async_session_maker", mock_failing_session_maker):
        test_app = FastAPI()
        with pytest.raises(RuntimeError) as excinfo:
            async with lifespan(test_app):
                pass
        assert "Production startup failed: Unable to connect to database" in str(excinfo.value)


@pytest.mark.asyncio
async def test_lifespan_logs_warning_on_unreachable_db_in_development(monkeypatch):
    """In development, an unreachable database logs warning and permits offline startup."""
    @asynccontextmanager
    async def mock_failing_session_maker():
        raise ConnectionRefusedError("Database connection refused")
        yield  # noqa

    monkeypatch.setattr("app.core.config.settings.CHECK_DB_ROLE_ON_STARTUP", True)
    monkeypatch.setattr("app.core.config.settings.ENVIRONMENT", "development")

    with patch("app.db.session.async_session_maker", mock_failing_session_maker):
        test_app = FastAPI()
        # Should not raise exception in development
        async with lifespan(test_app):
            pass

