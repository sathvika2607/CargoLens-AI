import asyncio
import os
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context

from app.config import settings
from app.models import Base

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# add your model's MetaData object here
# for 'autogenerate' support
target_metadata = Base.metadata


def get_migration_url(async_mode: bool = False) -> str:
    """
    Determines the database URL for migrations.
    Defaults to application database settings, with support for -x db_url=<url>,
    alembic.ini sqlalchemy.url override, or CARGOLENS_ALEMBIC_DATABASE_URL environment variable.
    """
    x_args = context.get_x_argument(as_dictionary=True)
    custom_url = (
        x_args.get("db_url")
        or config.get_main_option("sqlalchemy.url")
        or os.getenv("CARGOLENS_ALEMBIC_DATABASE_URL")
    )
    if custom_url:
        if async_mode and custom_url.startswith("postgresql://"):
            return custom_url.replace("postgresql://", "postgresql+asyncpg://", 1)
        elif not async_mode and custom_url.startswith("postgresql+asyncpg://"):
            return custom_url.replace("postgresql+asyncpg://", "postgresql://", 1)
        return custom_url
    return settings.async_database_url if async_mode else settings.sync_database_url


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = get_migration_url(async_mode=False)
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = get_migration_url(async_mode=True)

    connectable = async_engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
