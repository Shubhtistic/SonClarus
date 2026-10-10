from typing import Optional
from uuid import UUID
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from .models import User
from src.sonclarus.shared.database import (
    check_exists,
    create,
    execute_query,
    get_one_by_query,
)


class UserRepository:
    @staticmethod
    async def check_by_email(db_session: AsyncSession, email: str) -> bool:
        return await check_exists(
            model=User, db_session=db_session, filters={"email": email}
        )

    @staticmethod
    async def create_user(db_session: AsyncSession, instance: User) -> User:
        return await create(instance=instance, db_session=db_session)

    @staticmethod
    async def get_by_email(db_session: AsyncSession, email: str) -> Optional[User]:
        qry = select(User).where(User.email == email, User.is_active == True)
        return await get_one_by_query(qry, db_session)

    @staticmethod
    async def get_user_by_id(user_id: UUID, db_session: AsyncSession) -> Optional[User]:
        qry = select(User).where(User.id == user_id, User.is_active == True)
        return await get_one_by_query(qry, db_session)

    @staticmethod
    async def increment_user_storage(
        db_session: AsyncSession, user_id: UUID, delta_bytes: int
    ) -> bool:
        qry = (
            update(User)
            .where(
                User.id == user_id,
                User.storage_used + delta_bytes <= User.storage_limit,
            )
            .values(storage_used=User.storage_used + delta_bytes)
            .returning(User.id)
        )

        result = await execute_query(query=qry, db_session=db_session)
        return result.scalar_one_or_none() is not None
