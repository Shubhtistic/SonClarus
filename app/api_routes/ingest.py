# this endpoints takes the files and checks if it an valid wav file

import uuid
from fastapi import APIRouter, UploadFile, File, HTTPException, status

from app.db.db_models import Job, JobStatus
from app.dependancies.db_dependancy import DbSessionDep

import shutil
# shutil stand for shell utilities and its used for heavy tasks with files, like
# copying them , moving them, etc.

import os
# used to talk with the computer/our device create files or folders

# from uuid import uuid4

# uuid4 -> unique id with veruy low chance of replication

from app.schemas.file_upload import FileUpload
from app.config import settings

from celery import Celery

from app.dependancies.auth import CurrentUserDep

celery_client = Celery("worker", broker=settings.REDIS_URL, backend=settings.REDIS_URL)

UPLOAD_DIR = settings.FILE_UPLOAD_PATH

os.makedirs(UPLOAD_DIR, exist_ok=True)
# os tells the system to make an dir called as 'Upload_Dir' and
# then with exist_ok=true is it already present we ignore it


router = APIRouter()


@router.post("/uploads", response_model=FileUpload)
async def upload_audio(
    current_user: CurrentUserDep, db: DbSessionDep, file: UploadFile = File(...)
):  ### ... means this endpoint cant be hit without an file
    if not file.filename.endswith(".wav"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The provided File is Invalid.\nFile should be an audio file with '.wav' format",
        )

    job_id = uuid.uuid4()

    # Create a unique folder for this job so output files (PDFs) stay organized
    job_folder = os.path.join(UPLOAD_DIR, str(job_id))
    os.makedirs(job_folder, exist_ok=True)

    # os.path.join(): Safely combines the folder name and the filename.
    file_path = os.path.join(job_folder, file.filename)

    try:
        with open(file_path, "wb") as audio_file:
            shutil.copyfileobj(file.file, audio_file)
            # we copy the incoming file into our folder
    except Exception as e:
        shutil.rmtree(job_folder)  # Clean up if failed
        raise HTTPException(status_code=500, detail=f"Could not save file: {str(e)}")

    new_job = Job(
        id=job_id,
        filename=file.filename,
        filepath=file_path,
        user_id=current_user.id,
        status=JobStatus.PENDING,
    )
    db.add(new_job)
    await db.commit()
    await db.refresh(new_job)

    task = celery_client.send_task("process_forensics", args=[str(new_job.id)])

    return {
        "message": "Upload successful",
        "job_id": new_job.id,
        "status": "pending",
        "task_id": task.id,
    }
