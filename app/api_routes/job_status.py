# This endpoint checks the status and results for our job in the database
from fastapi import APIRouter, Depends, HTTPException, status
from app.dependancies.db_dependancy import DbSessionDep
from sqlalchemy.future import select
from app.db.db_models import Job, JobStatus

from app.dependancies.auth import CurrentVerifiedUserDep
from app.dependancies.rate_limit import check_limit

router = APIRouter()


@router.get("/status/{job_id}", dependencies=[Depends(check_limit(15))])
async def get_job_status(
    job_id: str, db: DbSessionDep, current_user: CurrentVerifiedUserDep
):
    sql_query = select(Job.id, Job.status, Job.user_id).where(job_id == Job.id)
    result = await db.execute(sql_query)
    job = result.one_or_none()

    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Job id not found"
        )

    # SECURITY CHECK: Does this job belong to the current user
    if job.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to view this job")

    return {
        "job_id": job.id,
        "status": job.status,
    }


@router.get("/result/{job_id}", dependencies=[Depends(check_limit(15))])
async def get_job_result(
    job_id: str, db: DbSessionDep, current_user: CurrentVerifiedUserDep
):
    sql_query = select(Job).where(job_id == Job.id)
    result = await db.execute(sql_query)
    job = result.scalar_one_or_none()

    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Job id not found"
        )

    if job.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to view this job")

    # If it's not done or failed, don't return the payload yet
    if job.status not in [JobStatus.DONE, JobStatus.FAILED]:
        return {
            "job_id": job.id,
            "status": job.status,
            "message": "Processing is not yet complete.",
        }

    return {
        "job_id": job.id,
        "status": job.status,
        "transcript": job.transcript,
        "summary": job.summary,
        "action_items": job.action_items,
        "error_message": job.error_message,
    }
