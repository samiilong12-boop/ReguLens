"""Unit tests for runtime database role verification and privilege enforcement."""
import pytest
from unittest.mock import AsyncMock, MagicMock
from app.db.session import verify_database_role


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
