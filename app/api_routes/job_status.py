# This endpoint check the status for our job in the database
from fastapi import APIRouter, HTTPException, status
from app.dependancies.db_dependancy import DbSessionDep
from sqlalchemy.future import select
from app.db.db_models import Job

from app.dependancies.auth import CurrentUserDep

router = APIRouter()


@router.get("/jobs/{job_id}")
async def get_job_status(job_id: str, db: DbSessionDep, current_user: CurrentUserDep):

    sql_query = select(Job).where(job_id == Job.id)

    result = await db.execute(sql_query)
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Job id not found"
        )

    # SECURITY CHECK: Does this job belong to the current user
    if job.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to view this job")

    return {
        "job_id": job.id,
        "filename": job.filename,
        "status": job.status,
        "created_at": job.created_at,
    }
