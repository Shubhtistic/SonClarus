# This endpoint check the status for our job in the database
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app.db.database_session import get_db_session
from app.db.db_models import ProcessJob

router = APIRouter()


@router.get("/jobs/{job_id}")
async def get_job_status(job_id: str, db: AsyncSession = Depends(get_db_session)):
    sql_query = select(ProcessJob).where(job_id == ProcessJob.job_id)

    result = await db.execute(sql_query)
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Job id not found"
        )

    return {
        "job_id": job.job_id,
        "filename": job.filename,
        "status": job.status,
        "created_at": job.timestamp,
    }
