"""
Regression Tests for CargoLens AI — Test Database Isolation & Data Protection.

Verifies:
1. Tests cannot initialize against 'cargolens_db'.
2. Missing test database configuration causes a clear, immediate failure.
3. The test database can be selected explicitly and sanitized.
4. Cleanup and destructive operations target ONLY the verified test database.
5. The application database URL and runtime configuration remain completely unchanged.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock
from sqlalchemy import text

from app.config import settings
from app.test_db_guard import (
    validate_test_database_url,
    extract_database_name,
    verify_connection_database_identity,
    TestDatabaseConfigurationError,
    DestructiveOperationBlockedError,
    TEST_DATABASE_ENV_VAR,
)


def test_cannot_initialize_against_cargolens_db():
    """
    Safety Invariant 1:
    Tests must strictly fail and reject any URL targeting 'cargolens_db'.
    """
    prohibited_urls = [
        "postgresql+asyncpg://cargolens_user:cargolens_dev_password@127.0.0.1:5432/cargolens_db",
        "postgresql://cargolens_user:cargolens_dev_password@127.0.0.1:5432/cargolens_db",
        "postgresql+asyncpg://user:pass@localhost:5432/CARGOLENS_DB",
        "postgresql://user:pass@localhost:5432/cargolens_db?ssl=false",
    ]
    for url in prohibited_urls:
        with pytest.raises(TestDatabaseConfigurationError) as exc_info:
            validate_test_database_url(
                test_db_url=url,
                app_db_url=settings.async_database_url,
                app_db_name=settings.POSTGRES_DB,
            )
        err_msg = str(exc_info.value).lower()
        assert "cargolens_db" in err_msg or "prohibited" in err_msg or "matches application" in err_msg


def test_missing_test_database_configuration_causes_clear_failure():
    """
    Safety Invariant 2:
    Tests must fail immediately if CARGOLENS_TEST_DATABASE_URL is missing or blank.
    Silent fallback to application database is strictly prohibited.
    """
    for invalid_val in [None, "", "   "]:
        with pytest.raises(TestDatabaseConfigurationError) as exc_info:
            validate_test_database_url(
                test_db_url=invalid_val,
                app_db_url=settings.async_database_url,
                app_db_name=settings.POSTGRES_DB,
            )
        err_msg = str(exc_info.value)
        assert TEST_DATABASE_ENV_VAR in err_msg
        assert "strictly prohibited from silently falling back" in err_msg


def test_test_database_can_be_selected_explicitly():
    """
    Safety Invariant 3:
    Isolated test database URL is accepted, normalized to asyncpg, and correctly parsed.
    """
    valid_url = "postgresql://cargolens_user:cargolens_dev_password@127.0.0.1:5432/cargolens_test_db"
    res = validate_test_database_url(
        test_db_url=valid_url,
        app_db_url=settings.async_database_url,
        app_db_name=settings.POSTGRES_DB,
    )
    assert res.startswith("postgresql+asyncpg://")
    assert extract_database_name(res) == "cargolens_test_db"

    # Custom isolated CI database names are supported
    ci_url = "postgresql+asyncpg://ci_user:ci_pass@db-host:5432/cargolens_ci_isolated_test_db"
    res_ci = validate_test_database_url(
        test_db_url=ci_url,
        app_db_url=settings.async_database_url,
        app_db_name=settings.POSTGRES_DB,
    )
    assert extract_database_name(res_ci) == "cargolens_ci_isolated_test_db"


@pytest.mark.asyncio
async def test_destructive_safety_check_blocks_prohibited_databases():
    """
    Safety Invariant 4:
    verify_connection_database_identity fails closed and blocks destructive operations
    if the connection is active on cargolens_db, postgres, or an unverified database.
    """
    # 1. Mock connection returning 'cargolens_db'
    mock_conn_app = AsyncMock()
    mock_res_app = MagicMock()
    mock_res_app.scalar.return_value = "cargolens_db"
    mock_conn_app.execute.return_value = mock_res_app

    with pytest.raises(DestructiveOperationBlockedError) as exc_info:
        await verify_connection_database_identity(mock_conn_app, expected_db_name="cargolens_test_db")
    assert "protected database" in str(exc_info.value).lower()
    assert "cargolens_db" in str(exc_info.value)

    # 2. Mock connection returning 'postgres'
    mock_conn_pg = AsyncMock()
    mock_res_pg = MagicMock()
    mock_res_pg.scalar.return_value = "postgres"
    mock_conn_pg.execute.return_value = mock_res_pg

    with pytest.raises(DestructiveOperationBlockedError) as exc_info:
        await verify_connection_database_identity(mock_conn_pg, expected_db_name="cargolens_test_db")
    assert "protected database" in str(exc_info.value).lower()

    # 3. Mock connection returning mismatched database name
    mock_conn_other = AsyncMock()
    mock_res_other = MagicMock()
    mock_res_other.scalar.return_value = "unexpected_random_db"
    mock_conn_other.execute.return_value = mock_res_other

    with pytest.raises(DestructiveOperationBlockedError) as exc_info:
        await verify_connection_database_identity(mock_conn_other, expected_db_name="cargolens_test_db")
    assert "unexpected_random_db" in str(exc_info.value)

    # 4. Fail-closed on query exception
    mock_conn_err = AsyncMock()
    mock_conn_err.execute.side_effect = RuntimeError("Connection severed")
    with pytest.raises(DestructiveOperationBlockedError) as exc_info:
        await verify_connection_database_identity(mock_conn_err, expected_db_name="cargolens_test_db")
    assert "fail-closed" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_live_connection_identity_confirms_isolated_test_database(db_session):
    """
    Safety Invariant 4 (Live Verification):
    Confirms that the active test database connection in pytest is physically
    connected to 'cargolens_test_db' and NOT 'cargolens_db'.
    """
    res = await db_session.execute(text("SELECT current_database();"))
    connected_db = res.scalar()

    assert connected_db == "cargolens_test_db", (
        f"CRITICAL VIOLATION: Test connection is active on '{connected_db}' instead of 'cargolens_test_db'!"
    )
    assert connected_db != "cargolens_db"
    assert connected_db != "postgres"


def test_application_database_url_and_runtime_configuration_remain_unchanged():
    """
    Safety Invariant 5:
    The application runtime settings and default database configuration remain
    strictly pointed to 'cargolens_db' and are never altered by test execution.
    """
    assert settings.POSTGRES_DB == "cargolens_db"
    assert "cargolens_db" in settings.async_database_url
    assert "cargolens_db" in settings.sync_database_url
    assert "cargolens_test_db" not in settings.async_database_url
    assert "cargolens_test_db" not in settings.sync_database_url
