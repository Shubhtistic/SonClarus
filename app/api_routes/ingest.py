# this endpoints takes the files and checks if it an valid wav file
from fastapi import APIRouter, Depends, HTTPException, status
from app.dependancies.auth import CurrentVerifiedUserDep

from uuid_utils import uuid7  # uuid7 -> unique id with almost no chance of replication
from app.db.db_models import Job, JobStatus
from app.dependancies.db_dependancy import DbSessionDep
from app.config import settings
from app.schemas.job_schema import UploadRequest
from sqlalchemy import select, delete, update
from app.dependancies.arq_redis import get_redis_pool

# rate limiter
from app.dependancies.rate_limit import check_limit

# s3 function
from app.core.aws_s3_utils import generate_presigned_post, verify_s3_upload

router = APIRouter()


@router.post("/uploads/request", dependencies=[Depends(check_limit(4))])
async def upload_audio(
    current_user: CurrentVerifiedUserDep, db: DbSessionDep, request: UploadRequest
):
    if not request.filename.endswith(".wav"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Invalid file format, Only .wav files are Allowed.",
        )

    job_id = str(uuid7())
    user_id = str(current_user.id)

    presigned_data = await generate_presigned_post(
        user_id=user_id, job_id=job_id, filename=request.filename, expires_in=600
    )

    # Use just the key for provider-agnostic storage
    s3_key = f"{user_id}/{job_id}/original/{request.filename}"

    new_job = Job(
        id=job_id,
        filename=request.filename,
        object_key=s3_key,
        user_id=current_user.id,
        status=JobStatus.QUEUED,
    )

    db.add(new_job)
    await db.commit()

    return {"job_id": job_id, "presigned_post": presigned_data}


@router.post("/uploads/confirm/{job_id}", dependencies=[Depends(check_limit(10))])
async def confirm_upload(
    job_id: str, db: DbSessionDep, current_user: CurrentVerifiedUserDep
):
    user_id = str(current_user.id)
    # check if job exists
    qry = select(Job.status, Job.filename).where(
        Job.user_id == user_id, Job.id == job_id
    )

    job_res = (await db.execute(qry)).one_or_none()

    if not job_res:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="The file Does not exist"
        )

    if job_res.status != JobStatus.QUEUED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The job is not in queued state",
        )

    # s3 verification
    is_uploaded = await verify_s3_upload(
        user_id=user_id, job_id=job_id, filename=job_res.filename
    )

    if not is_uploaded:
        # as file is not found on s3 lets delete the record from db as well
        qry = delete(Job).where(Job.id == job_id, Job.user_id == user_id)
        await db.execute(qry)
        await db.commit()

        # return the error code
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Object Not found, Incomplete User Upload",
        )

    # the file exists on s3. It is already marked QUEUED, so we just hand it to the worker.
    arq_pool = await get_redis_pool()
    await arq_pool.enqueue_job("process_audios_pipeline", job_id)

    return {
        "message": "Upload confirmed and processing enqueued.",
        "job_id": job_id,
        "status": JobStatus.QUEUED,
    }
