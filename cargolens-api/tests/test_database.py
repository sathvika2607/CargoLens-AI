import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy import Column, Integer, String
from alembic.config import Config
from app.models.base import Base, TimestampMixin
from app.database import check_database_connection, get_async_session, dispose_engine


class DummyModel(Base, TimestampMixin):
    __tablename__ = "test_dummy_model"
    id = Column(Integer, primary_key=True)
    name = Column(String(50), nullable=False)


def test_declarative_base_model_metadata():
    """Verifies that Base is an active DeclarativeBase and tracks table definitions."""
    assert "test_dummy_model" in Base.metadata.tables
    table = Base.metadata.tables["test_dummy_model"]
    assert "created_at" in table.columns
    assert "updated_at" in table.columns


def test_alembic_configuration_and_metadata():
    """Verifies that alembic.ini is valid and Base.metadata contains defined models."""
    config = Config("alembic.ini")
    assert config.get_main_option("script_location") == "alembic"
    from app.models import Base as AppBase
    assert "test_dummy_model" in AppBase.metadata.tables


@pytest.mark.asyncio
async def test_session_lifecycle_and_cleanup():
    """Verifies that get_async_session yields a session and closes it cleanly."""
    mock_session = AsyncMock()
    mock_context = MagicMock()
    mock_context.__aenter__.return_value = mock_session
    mock_context.__aexit__.return_value = None

    with patch("app.database.AsyncSessionFactory", return_value=mock_context):
        async_gen = get_async_session()
        session = await anext(async_gen)
        assert session is mock_session
        try:
            await anext(async_gen)
        except StopAsyncIteration:
            pass
        mock_session.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_check_database_connection_failure():
    """Verifies that check_database_connection returns connected=False on exception."""
    with patch("app.database.AsyncSessionFactory") as mock_factory:
        mock_session = AsyncMock()
        mock_session.execute.side_effect = ConnectionRefusedError("Could not connect to server")
        mock_factory.return_value.__aenter__.return_value = mock_session

        result = await check_database_connection()
        assert result["connected"] is False
        assert "Could not connect to server" in result["error"]


@pytest.mark.asyncio
async def test_real_database_connectivity():
    """
    Direct integration test verifying actual connection to PostgreSQL via asyncpg.
    Enforces a strict 5-second timeout and clean engine disposal.
    """
    try:
        result = await asyncio.wait_for(check_database_connection(), timeout=5.0)
        assert result["connected"] is True
        assert result["dialect"] == "postgresql"
        assert result["latency_ms"] is not None
        assert result["latency_ms"] > 0
        assert result["error"] is None
    finally:
        await dispose_engine()
