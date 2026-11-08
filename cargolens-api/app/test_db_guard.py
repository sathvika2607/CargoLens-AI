"""
CargoLens AI — Test Database Isolation & Destructive Operation Safety Guard.

Guarantees physical and architectural isolation between the application database
('cargolens_db') and the automated test database ('cargolens_test_db').

Safety invariants enforced by this module:
1. Tests must NEVER connect to, query, or execute against 'cargolens_db'.
2. CARGOLENS_TEST_DATABASE_URL environment variable is mandatory for all test runs.
3. If CARGOLENS_TEST_DATABASE_URL is missing or points to 'cargolens_db', tests fail immediately.
4. Silent fallback to the application DATABASE_URL is strictly prohibited.
5. All destructive test operations (TRUNCATE, DROP) must verify the physical database identity
   via `SELECT current_database()` on the active connection before execution, failing closed
   if identity cannot be verified or if the database is 'cargolens_db'.
"""
import logging
from typing import Optional
from urllib.parse import urlparse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

logger = logging.getLogger("cargolens.test_db_guard")

PROHIBITED_DATABASES = {"cargolens_db", "postgres"}
TEST_DATABASE_ENV_VAR = "CARGOLENS_TEST_DATABASE_URL"
DEFAULT_TEST_DB_NAME = "cargolens_test_db"


class TestDatabaseConfigurationError(Exception):
    """Raised when test database isolation configuration is missing, invalid, or unsafe."""
    __test__ = False


class DestructiveOperationBlockedError(Exception):
    """Raised when a destructive operation is attempted against a prohibited or unverified database."""
    pass


def extract_database_name(url: Optional[str]) -> str:
    """
    Extracts and standardizes the database name component from a database connection URL.
    Returns lowercase stripped database name, or empty string if invalid.
    """
    if not url or not isinstance(url, str):
        return ""
    try:
        parsed = urlparse(url)
        db_name = parsed.path.lstrip("/").split("?")[0].strip().lower()
        return db_name
    except Exception:
        return ""


def validate_test_database_url(
    test_db_url: Optional[str],
    app_db_url: Optional[str] = None,
    app_db_name: str = "cargolens_db",
) -> str:
    """
    Validates that CARGOLENS_TEST_DATABASE_URL is provided, valid, and strictly isolated
    from the application database.

    Returns the normalized asyncpg URL string.
    Raises TestDatabaseConfigurationError on any safety violation.
    """
    if not test_db_url or not test_db_url.strip():
        raise TestDatabaseConfigurationError(
            f"CRITICAL TEST ISOLATION ERROR: Missing '{TEST_DATABASE_ENV_VAR}' environment variable. "
            "Tests are strictly prohibited from silently falling back to the application database ('cargolens_db'). "
            f"Set {TEST_DATABASE_ENV_VAR}=postgresql+asyncpg://<user>:<password>@<host>:<port>/{DEFAULT_TEST_DB_NAME} "
            "to run automated tests."
        )

    clean_url = test_db_url.strip()
    test_db_name = extract_database_name(clean_url)

    if not test_db_name:
        raise TestDatabaseConfigurationError(
            f"CRITICAL TEST ISOLATION ERROR: {TEST_DATABASE_ENV_VAR} is missing a database name: '{clean_url}'"
        )

    # Invariant 1: Prohibited database check
    if test_db_name in PROHIBITED_DATABASES:
        raise TestDatabaseConfigurationError(
            f"CRITICAL SAFETY VIOLATION: {TEST_DATABASE_ENV_VAR} targets prohibited database '{test_db_name}'. "
            "Automated tests are strictly prohibited from running against the application database ('cargolens_db') "
            "or system databases. Use a dedicated test database such as 'cargolens_test_db'."
        )

    # Invariant 2: App database name match check
    if app_db_name and test_db_name == app_db_name.strip().lower():
        raise TestDatabaseConfigurationError(
            f"CRITICAL SAFETY VIOLATION: {TEST_DATABASE_ENV_VAR} database '{test_db_name}' matches application "
            f"database '{app_db_name}'. Tests must run against an isolated test database."
        )

    # Invariant 3: App database URL match check (accounting for driver prefix differences)
    if app_db_url:
        norm_test = clean_url.replace("postgresql+asyncpg://", "postgresql://").rstrip("/")
        norm_app = app_db_url.replace("postgresql+asyncpg://", "postgresql://").rstrip("/")
        if norm_test == norm_app:
            raise TestDatabaseConfigurationError(
                "CRITICAL SAFETY VIOLATION: Test database URL is identical to the application database URL. "
                "Tests must use a separate database instance/name."
            )

    # Ensure asyncpg driver prefix for async SQLAlchemy engines
    if clean_url.startswith("postgresql://"):
        clean_url = clean_url.replace("postgresql://", "postgresql+asyncpg://", 1)

    return clean_url


async def verify_connection_database_identity(
    conn: AsyncConnection,
    expected_db_name: str,
) -> str:
    """
    Executes 'SELECT current_database()' on the active connection.
    Verifies that the connected database:
    1. Is physically the expected test database.
    2. Is NOT 'cargolens_db' or any prohibited database.

    Fails closed if the identity cannot be verified.
    Returns the verified database name.
    """
    try:
        res = await conn.execute(text("SELECT current_database();"))
        actual_db = res.scalar()
    except Exception as exc:
        raise DestructiveOperationBlockedError(
            f"FAIL-CLOSED: Could not verify database identity on active connection: {exc}"
        ) from exc

    if not actual_db:
        raise DestructiveOperationBlockedError(
            "FAIL-CLOSED: Query 'SELECT current_database()' returned an empty result. Operation blocked."
        )

    actual_db_clean = actual_db.strip().lower()

    # Reject prohibited application databases
    if actual_db_clean in PROHIBITED_DATABASES:
        raise DestructiveOperationBlockedError(
            f"CRITICAL SAFETY VIOLATION: Connected database is '{actual_db}', which is a protected database! "
            "Destructive operations (TRUNCATE/DROP) and tests are strictly prohibited on this database."
        )

    # Enforce match with expected test database
    expected_clean = expected_db_name.strip().lower()
    if actual_db_clean != expected_clean:
        raise DestructiveOperationBlockedError(
            f"CRITICAL SAFETY VIOLATION: Active database connection is on '{actual_db}', but expected test database is '{expected_db_name}'. "
            "Destructive operation blocked to prevent accidental cross-database damage."
        )

    return actual_db
