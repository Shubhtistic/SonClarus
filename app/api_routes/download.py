from fastapi import APIRouter, status, HTTPException, Depends
from app.dependancies.auth import CurrentVerifiedUserDep
from app.dependancies.db_dependancy import DbSessionDep
from app.dependancies.rate_limit import check_limit
from app.schemas.stage_options import StageOptions
from sqlalchemy import select
from app.db.db_models import Job
from app.core.aws_s3_utils import generate_presigned_get
from app.db.db_models import JobStatus

router = APIRouter()


@router.get("/download/{job_id}", dependencies=[Depends(check_limit(12))])
async def download_file(
    job_id: str,
    stage: StageOptions,
    user: CurrentVerifiedUserDep,
    db: DbSessionDep,
):
    """verify user and generate download url"""
    user_id = str(user.id)

    qry = select(Job.filename, Job.status).where(
        Job.id == job_id, Job.user_id == user_id
    )
    res = (await db.execute(qry)).one_or_none()

    if not res:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Job Not found"
        )
    if res.status != JobStatus.DONE:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Job Not completed"
        )

    # remove the wav from file
    base_name = res.filename.rsplit(".", 1)[0]

    if stage == StageOptions.separated1:
        filename = f"{base_name}_cleaned_speaker_1.wav"
        url = await generate_presigned_get(
            user_id=user_id, stage_name="separated", job_id=job_id, filename=filename
        )
        return {"download_url": url}

    elif stage == StageOptions.separated2:
        filename = f"{base_name}_cleaned_speaker_2.wav"
        url = await generate_presigned_get(
            user_id=user_id, stage_name="separated", job_id=job_id, filename=filename
        )
        return {"download_url": url}

    elif stage == StageOptions.transcribe:
        filename = f"{base_name}_full_script.txt"
        url = await generate_presigned_get(
            user_id=user_id, stage_name="transcribe", job_id=job_id, filename=filename
        )
        return {"download_url": url}
