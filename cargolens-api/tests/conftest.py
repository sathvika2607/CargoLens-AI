"""
CargoLens AI — Pytest Configuration with Enforced Test Database Isolation.

This configuration enforces physical isolation between the application database
('cargolens_db') and the test database ('cargolens_test_db').

Safety invariants:
- CARGOLENS_TEST_DATABASE_URL must be explicitly provided in the environment.
- Tests will fail immediately if CARGOLENS_TEST_DATABASE_URL is missing or targets 'cargolens_db'.
- All test fixtures, client calls, background services, and destructive cleanups
  are strictly confined to the isolated test database.
- Destructive truncation checks `current_database()` before execution and fails closed.
"""
import asyncio
import concurrent.futures
import os
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy import text
from sqlalchemy.pool import NullPool
from sqlalchemy.ext.asyncio import (
    create_async_engine,
    async_sessionmaker,
    AsyncSession,
    AsyncEngine,
)

from app.config import settings
from app.test_db_guard import (
    validate_test_database_url,
    extract_database_name,
    verify_connection_database_identity,
    TEST_DATABASE_ENV_VAR,
)

# ------------------------------------------------------------------------------
# 1. Enforce Test Database Isolation at Module Load Time
# ------------------------------------------------------------------------------
raw_test_db_url = os.getenv(TEST_DATABASE_ENV_VAR)
verified_test_db_url = validate_test_database_url(
    test_db_url=raw_test_db_url,
    app_db_url=settings.async_database_url,
    app_db_name=settings.POSTGRES_DB,
)
expected_test_db_name = extract_database_name(verified_test_db_url)

# ------------------------------------------------------------------------------
# 2. Configure Dedicated Test Engine and Session Factory
# ------------------------------------------------------------------------------
test_async_engine: AsyncEngine = create_async_engine(
    verified_test_db_url,
    poolclass=NullPool,
    echo=False,
    connect_args={"timeout": 30},
)

TestAsyncSessionFactory = async_sessionmaker(
    bind=test_async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

# Rebind app.database global engine and session factory to test database
# Ensures that background jobs, worker leases, and seed routines operate on test DB
import app.database
app.database.async_engine = test_async_engine
app.database.AsyncSessionFactory = TestAsyncSessionFactory

from app.main import app


async def test_get_async_session():
    """Dependency override ensuring all FastAPI endpoint handlers use the test session."""
    async with TestAsyncSessionFactory() as session:
        yield session


from app.database import get_async_session
app.dependency_overrides[get_async_session] = test_get_async_session


# ------------------------------------------------------------------------------
# 3. Session-Scoped Fixture: Verify Identity & Migrate Test Database
# ------------------------------------------------------------------------------
@pytest_asyncio.fixture(scope="session", autouse=True)
async def initialize_test_database():
    """
    Verifies that the connection is active on the expected isolated test database,
    and ensures all Alembic migrations are applied up to head on the test database.
    """
    async with test_async_engine.connect() as conn:
        # Strict destructive/identity safety check
        await verify_connection_database_identity(conn, expected_test_db_name)

        # Check if migrations are present
        res = await conn.execute(
            text(
                "SELECT EXISTS ("
                "  SELECT FROM information_schema.tables "
                "  WHERE table_schema = 'public' AND table_name = 'alembic_version'"
                ");"
            )
        )
        has_alembic = res.scalar()

    if not has_alembic:
        from alembic import command
        from alembic.config import Config

        def _run_upgrade():
            alembic_cfg = Config("alembic.ini")
            sync_test_url = verified_test_db_url.replace("postgresql+asyncpg://", "postgresql://", 1)
            alembic_cfg.set_main_option("sqlalchemy.url", sync_test_url)
            command.upgrade(alembic_cfg, "head")

        loop = asyncio.get_running_loop()
        with concurrent.futures.ThreadPoolExecutor() as executor:
            await loop.run_in_executor(executor, _run_upgrade)

    yield

    await test_async_engine.dispose()


# ------------------------------------------------------------------------------
# 4. Per-Test Fixture: Clean Isolated Test Database
# ------------------------------------------------------------------------------
@pytest_asyncio.fixture(autouse=True)
async def clean_database_fixture():
    """
    Wipes test tables after each test run with mandatory safety verification.
    Guarantees that cleanup NEVER touches 'cargolens_db'.
    """
    yield
    async with test_async_engine.begin() as conn:
        await verify_connection_database_identity(conn, expected_test_db_name)
        await conn.execute(
            text(
                "TRUNCATE TABLE shipment_export_records, document_field_reviews, "
                "shipment_validation_results, structured_extractions, document_extraction_pages, "
                "document_extractions, processing_jobs, documents, shipments, refresh_tokens, users "
                "RESTART IDENTITY CASCADE;"
            )
        )


# ------------------------------------------------------------------------------
# 5. Shared Test Fixtures
# ------------------------------------------------------------------------------
@pytest_asyncio.fixture
async def async_client():
    """Provides an asynchronous HTTP test client for the FastAPI application."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client


@pytest_asyncio.fixture
async def db_session():
    """Provides an active database session bound exclusively to the test database."""
    async with TestAsyncSessionFactory() as session:
        yield session
