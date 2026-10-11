from datetime import datetime
from typing import Optional
from uuid import UUID

import orjson
from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.sonclarus.jobs.models import Job
from src.sonclarus.jobs.enums import JobStatus, StageName
from src.sonclarus.shared.database import create, execute_query
from src.sonclarus.shared.redis_client import get_redis


def _download_links_cache_key(job_id: str) -> str:
    return f"download_links:{job_id}"


class JobRepository:
    @staticmethod
    async def create_job(db_session: AsyncSession, instance: Job) -> Job:
        return await create(instance=instance, db_session=db_session)

    @staticmethod
    async def get_job_for_user(
        db_session: AsyncSession, job_id: UUID, user_id: UUID
    ) -> Optional[Job]:
        qry = select(Job).where(Job.id == job_id, Job.user_id == user_id)
        result = await db_session.execute(qry)
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
    async def get_cached_download_links(job_id: str) -> Optional[dict]:
        """Return cached download links dict or None if not cached."""
        redis = get_redis()
        raw = await redis.get(_download_links_cache_key(job_id))
        if raw is None:
            return None
        return orjson.loads(raw)

    @staticmethod
    async def set_cached_download_links(
        job_id: str, links: dict, ttl_seconds: int
    ) -> None:
        """Cache download links dict with the same TTL as the presigned URLs."""
        redis = get_redis()
        await redis.setex(
            _download_links_cache_key(job_id),
            ttl_seconds,
            orjson.dumps(links),
        )
