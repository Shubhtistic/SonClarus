from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession

from src.sonclarus.jobs.services import JobService

from .models import User
from .repository import UserRepository
from .exceptions import UserAlreadyExistsError, UserNotFoundError
from .schemas import UserResponse, UserStatsResponse


class UserService:
    @staticmethod
    async def create_user(db_session: AsyncSession, user_data: dict) -> User:
        if await UserRepository.check_by_email(
            db_session=db_session, email=user_data["email"]
        ):
            raise UserAlreadyExistsError(email=user_data["email"])

        new_user = await UserRepository.create_user(
            db_session=db_session, instance=User(**user_data)
        )
        return new_user

    @staticmethod
    async def get_by_email(db_session: AsyncSession, email: str) -> User:
        if not (
            user := await UserRepository.get_by_email(
                db_session=db_session, email=email
            )
        ):
            raise UserNotFoundError(identifier=email)

        return user

    @staticmethod
    async def get_user_info_by_id(user_id: UUID, db_session: AsyncSession) -> dict:
        user = await UserRepository.get_user_by_id(
            user_id=user_id, db_session=db_session
        )
        if not user:
            raise UserNotFoundError(identifier=str(user_id))

        return UserResponse.model_validate(user).model_dump()

    @staticmethod
    async def get_user_stats(
        current_verified_user: dict, db_session: AsyncSession
    ) -> dict:

        try:
            user_id = UUID(current_verified_user.get("user_id"))
        except ValueError, TypeError:
            raise

        jobs_count = await JobService.get_jobs_count_for_user(
            user_id=user_id, db_session=db_session
        )

        return UserStatsResponse(
            jobs_completed=jobs_count.get("jobs_completed"),
            jobs_processing=jobs_count.get("jobs_processing"),
            storage_limit=current_verified_user.get("storage_limit"),
            storage_used=current_verified_user.get("storage_used"),
        ).model_dump()
