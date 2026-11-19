from typing import TypeVar

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import SQLModel

Model = TypeVar("Model", bound=SQLModel)


async def create[Model: SQLModel](instance: Model, db_session: AsyncSession) -> Model:
    db_session.add(instance)
    await db_session.flush()
    await db_session.refresh(instance)
    return instance


async def get_all(stmt: Select, db_session: AsyncSession) -> list[Model]:
    result = await db_session.execute(stmt)
    return result.scalars().all()


async def check_exists[Model: SQLModel](
    model: type[Model], db_session: AsyncSession, filters: dict | None = None
) -> bool:
    stmt = select(1).select_from(model).limit(1)
    for key, value in (filters or {}).items():
        stmt = stmt.where(getattr(model, key) == value)
    result = await db_session.execute(stmt)
    return result.scalar() is not None


async def get_one_by_query(q: Select, db_session: AsyncSession):
    result = await db_session.execute(q)
    return result.scalar_one_or_none()


async def execute_query(query, db_session: AsyncSession):
    return await db_session.execute(query)
