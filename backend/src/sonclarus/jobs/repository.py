from datetime import datetime
import logging
from typing import Optional
from uuid import UUID

import orjson
from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.sonclarus.jobs.models import Job
from src.sonclarus.jobs.enums import JobStatus, StageName
from src.sonclarus.shared.database import create, execute_query, get_one_by_query
from src.sonclarus.shared.redis_client import get_redis

logger = logging.getLogger(__name__)


def _download_links_cache_key(user_id: UUID, job_id: UUID) -> str:
    return f"jobs:download-links:{user_id}:{job_id}"


class JobRepository:
    @staticmethod
    async def create_job(db_session: AsyncSession, instance: Job) -> Job:
        return await create(instance=instance, db_session=db_session)

    @staticmethod
    async def get_job_for_user(
        db_session: AsyncSession, job_id: UUID, user_id: UUID
    ) -> Optional[Job]:
        qry = select(Job).where(Job.id == job_id, Job.user_id == user_id)
        return await get_one_by_query(q=qry, db_session=db_session)

    @staticmethod
    async def get_job_for_ml_result(
        db_session: AsyncSession, job_id: UUID, user_id: UUID
    ) -> Optional[Job]:
        """Load and lock a job before applying one ML stage result."""
        qry = (
            select(Job)
            .where(Job.id == job_id, Job.user_id == user_id)
            .with_for_update()
        )
        result = await execute_query(query=qry, db_session=db_session)
        return result.scalar_one_or_none()

    @staticmethod
    async def delete_job(db_session: AsyncSession, job_id: UUID, user_id: UUID) -> None:
        qry = delete(Job).where(Job.id == job_id, Job.user_id == user_id)
        await execute_query(query=qry, db_session=db_session)

    @staticmethod
    async def confirm_job_and_update(
        db_session: AsyncSession,
        job_id: UUID,
        user_id: UUID,
        file_metadata: dict,
        stages: dict,
        current_stage: StageName,  # first selected stage, the one published to Kafka
        uploaded_at: datetime,
    ) -> bool:

        qry = (
            update(Job)
            .where(
                Job.id == job_id,
                Job.user_id == user_id,
                Job.status == JobStatus.PENDING_UPLOAD,
            )
            .values(
                file_metadata=file_metadata,
                status=JobStatus.QUEUED,
                uploaded_at=uploaded_at,
                stages=stages,
                current_stage=current_stage,
            )
            .returning(Job.id)
        )
        result = await execute_query(query=qry, db_session=db_session)
        return result.scalar_one_or_none() is not None

    @staticmethod
    async def get_cached_download_links(user_id: UUID, job_id: UUID) -> Optional[dict]:
        """Return cached download data, if it is still available."""
        redis = get_redis()
        raw = await redis.get(_download_links_cache_key(user_id, job_id))
        if raw is None:
            return None
        return orjson.loads(raw)

    @staticmethod
    async def set_cached_download_links(
        user_id: UUID, job_id: UUID, data: dict, ttl_seconds: int
    ) -> None:
        """Cache the signed links until their S3 signatures expire."""
        redis = get_redis()
        await redis.setex(
            _download_links_cache_key(user_id, job_id),
            ttl_seconds,
            orjson.dumps(data),
        )
