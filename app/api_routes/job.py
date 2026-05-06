# This endpoint returns jobs and their status
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy import func
from app.dependancies.db_dependancy import DbSessionDep
from sqlalchemy.future import select
from app.db.db_models import Job, JobStatus

from app.dependancies.auth import CurrentVerifiedUserDep
from app.dependancies.rate_limit import check_limit

router = APIRouter()


@router.get("/jobs", dependencies=[Depends(check_limit(20))])
async def get_user_jobs(
    user: CurrentVerifiedUserDep,
    db: DbSessionDep,
    skip: int = Query(0, ge=0),
    limit: int = Query(5, ge=1, le=20),
    sort: str = Query("desc", pattern="^(asc|desc)$"),
):
    """Fetch jobs for the user, including the summary"""
    user_id = user.id

    # base query for user
    base_qry = select(Job).where(Job.user_id == user_id)

    # total count
    count_qry = select(func.count()).select_from(base_qry.subquery())
    total_count = (await db.execute(count_qry)).scalar()

    # data to be returned to frontend
    data_qry = select(
        Job.id,
        Job.filename,
        Job.summary,
        Job.created_at,
    ).where(Job.user_id == user_id)

    # Apply sorting
    if sort == "desc":
        data_qry = data_qry.order_by(Job.created_at.desc())
    else:
        data_qry = data_qry.order_by(Job.created_at.asc())

    # skip and limit
    data_qry = data_qry.offset(skip).limit(limit)

    # Execute the query
    result = await db.execute(data_qry)
    jobs = result.all()

    return {
        "total": total_count,
        "skip": skip,
        "limit": limit,
        "data": [
            {
                "job_id": str(job.id),
                "filename": job.filename,
                "summary": job.summary,
                "created_at": job.created_at,
            }
            for job in jobs
        ],
    }


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

    # imp ->  Does this job belong to the current user
    if job.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to view this job")

    return {
        "job_id": job.id,
        "status": job.status,
    }
