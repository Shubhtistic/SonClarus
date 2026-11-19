from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from src.sonclarus.infrastructure.config import get_settings

# --- settings ---
settings = get_settings()

# --- Engine ----
db_engine = create_async_engine(
    settings.postgres.postgres_async_url,
    echo=False,
    pool_size=settings.postgres.pool_size,
    max_overflow=settings.postgres.max_overflow,
    pool_timeout=settings.postgres.pool_timeout,
    pool_recycle=settings.postgres.pool_recycle,
    pool_pre_ping=settings.postgres.pool_pre_ping,
)


# --- session factory ----
SessionFactory = async_sessionmaker(
    bind=db_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


# --- transaction context ---
@asynccontextmanager
async def get_db_session() -> AsyncGenerator[AsyncSession]:
    """Open one session and transaction for an application operation."""
    async with SessionFactory() as db_session, db_session.begin():
        yield db_session
