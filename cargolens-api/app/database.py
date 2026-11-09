import time
import logging
from typing import AsyncGenerator, Dict, Any
from sqlalchemy.ext.asyncio import (
    create_async_engine,
    async_sessionmaker,
    AsyncSession,
    AsyncEngine,
)
from sqlalchemy import text
from app.config import settings
logger = logging.getLogger(__name__)

logger.warning(
    "DATABASE CONFIG CHECK: host=%r port=%r db=%r user_configured=%s password_configured=%s",
    settings.POSTGRES_SERVER,
    settings.POSTGRES_PORT,
    settings.POSTGRES_DB,
    bool(settings.POSTGRES_USER),
    bool(settings.POSTGRES_PASSWORD),
)

# Create async engine with connection pooling and pre-ping
async_engine: AsyncEngine = create_async_engine(
    settings.async_database_url,
    echo=False,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
    connect_args={"timeout": 5},
)

# Async session factory
AsyncSessionFactory = async_sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """Dependency that yields an async database session and ensures proper closure."""
    async with AsyncSessionFactory() as session:
        try:
            yield session
        finally:
            await session.close()


async def check_database_connection() -> Dict[str, Any]:
    """
    Tests direct connectivity to the PostgreSQL database by executing SELECT 1.
    Returns connectivity status, dialect, and latency in milliseconds.
    """
    start_time = time.perf_counter()
    try:
        async with AsyncSessionFactory() as session:
            result = await session.execute(text("SELECT 1;"))
            val = result.scalar()
            elapsed_ms = (time.perf_counter() - start_time) * 1000

            if val == 1:
                return {
                    "connected": True,
                    "dialect": async_engine.dialect.name,
                    "latency_ms": round(elapsed_ms, 2),
                    "error": None,
                }
            else:
                return {
                    "connected": False,
                    "dialect": async_engine.dialect.name,
                    "latency_ms": round(elapsed_ms, 2),
                    "error": f"Unexpected scalar result: {val}",
                }
    except Exception as exc:
        elapsed_ms = (time.perf_counter() - start_time) * 1000
        return {
            "connected": False,
            "dialect": async_engine.dialect.name,
            "latency_ms": round(elapsed_ms, 2),
            "error": str(exc),
        }


async def dispose_engine() -> None:
    """Closes all checked out and pooled connections upon application shutdown."""
    await async_engine.dispose()
