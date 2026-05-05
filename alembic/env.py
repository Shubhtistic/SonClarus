import asyncio
from logging.config import fileConfig
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import create_async_engine
from alembic import context

# 1. IMPORT ALL MODELS & SQLMODEL
from app.config import settings

# CRITICAL: Import your models here so they register with SQLModel.metadata
from app.db.db_models import User, Job, RefreshToken, SQLModel

# Access to the values within the .ini file
config = context.config

# Setup loggers
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# 1. SET TARGET METADATA
target_metadata = SQLModel.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    # 2. DIRECTLY USE settings.POSTGRES_URL
    context.configure(
        url=settings.POSTGRES_URL,
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
    """Run migrations in 'online' mode using Async Engine."""

    # 3. REPLACE WITH create_async_engine(settings.POSTGRES_URL)
    connectable = create_async_engine(settings.POSTGRES_URL)

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
