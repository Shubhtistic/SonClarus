# this endpoints takes the files and checks if it an valid wav file

from fastapi import APIRouter, UploadFile, File, HTTPException, status

import shutil
# shutil stand for shell utilities and its used for heavy tasks with files, like
# copying them , moving them, etc.

import os
# used to talk with the computer/our device create files or folders

from uuid import uuid4

# uuid4 -> unique id with veruy low chance of replication

from app.schemas.file_upload import FileUpload
from app.config import settings


UPLOAD_DIR = settings.FILE_UPLOAD_PATH

os.makedirs(UPLOAD_DIR, exist_ok=True)
# os tells the system to make an dir called as 'Upload_Dir' and
# then with exist_ok=true is it already present we ignore it

router = APIRouter()


@router.post("/uploads", response_model=FileUpload)
async def upload_audio(
    file: UploadFile = File(...),
):  ### ... means this endpoint cant be hit without an file
    if not file.filename.endswith(".wav"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The provided File is Invalid.\nFile should be an audio file with '.wav' format",
        )
    job_id = str(uuid4())[:16]

    new_filename = f"{file.filename}_{job_id}"

    file_path = os.path.join(UPLOAD_DIR, new_filename)
    # os.path.join(): Safely combines the folder name and the filename.

    with open(file_path, "wb") as audio_file:
        shutil.copyfileobj(file.file, audio_file)
        # we copy the incoming file into our folder

    return FileUpload(
        job_id=job_id,
        status="PENDING",
        filename=new_filename,
        message="File ingested successfully.",
    )
