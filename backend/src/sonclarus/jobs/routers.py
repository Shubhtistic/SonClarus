import logging
from uuid import UUID
from fastapi import APIRouter, Depends, Query

from src.sonclarus.shared.database import DbSessionDep
from src.sonclarus.shared.responses import ApiResponse
from src.sonclarus.auth.dependencies import CurrentUserDep, VerifiedCurrentUserDep
from .schemas import UploadRequestSchema
from .services import JobService
from .exceptions import (
    InsufficientStorageError,
    JobNotCompletedError,
    JobNotFoundError,
    JobNotQueuedError,
    UploadNotFoundOnS3Error,
    ActualSizeExceedsStorageError,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.post("/request-upload")
async def request_upload(
    payload: UploadRequestSchema,
    db_session: DbSessionDep,
    current_user: VerifiedCurrentUserDep,
):
    user_id = UUID(current_user.get("user_id"))
    logger.info("current_user keys: %s", list(current_user.keys()))

    try:
        data = await JobService.request_upload(
            db_session=db_session,
            user_id=user_id,
            storage_limit=current_user.get("storage_limit"),
            storage_used=current_user.get("storage_used"),
            payload=payload,
        )

    except InsufficientStorageError as e:
        remaining_mb = e.remaining_bytes / (1024 * 1024)
        return ApiResponse.error(
            message=f"Not enough storage. You have {remaining_mb:.2f} MB left",
            code=413,
        )

    return ApiResponse.success(message="Upload URL generated", data=data, code=201)


@router.post("/{job_id}/confirm-upload")
async def confirm_upload(
    job_id: str,
    db_session: DbSessionDep,
    current_user: VerifiedCurrentUserDep,
):
    try:
        user_id = UUID(current_user.get("user_id"))
        job_uuid = UUID(job_id)
    except (TypeError, ValueError):
        return ApiResponse.error(message="Invalid id format", code=422)

    try:
        data = await JobService.confirm_upload(
            db_session=db_session,
            user_id=user_id,
            storage_limit=current_user.get("storage_limit"),
            storage_used=current_user.get("storage_used"),
            job_id=job_uuid,
        )
    except JobNotFoundError:
        return ApiResponse.error(message="Job not found", code=404)
    except JobNotQueuedError:
        return ApiResponse.error(
            message="Job is not awaiting upload confirmation", code=400
        )
    except UploadNotFoundOnS3Error:
        return ApiResponse.error(
            message="File not found on S3, upload incomplete", code=404
        )
    except ActualSizeExceedsStorageError:
        return ApiResponse.error(
            message="Uploaded file exceeds your storage quota, file has been deleted",
            code=413,
        )

    return ApiResponse.success(message="Upload confirmed", data=data)


@router.get("/{job_id}/download-links")
async def get_download_links(
    job_id: str,
    db_session: DbSessionDep,
    current_user: VerifiedCurrentUserDep,
):
    try:
        user_id = UUID(current_user.get("user_id"))
        job_uuid = UUID(job_id)
    except (TypeError, ValueError):
        return ApiResponse.error(message="Invalid id format", code=422)

    try:
        data = await JobService.get_download_links(
            db_session=db_session,
            user_id=user_id,
            job_id=job_uuid,
        )
    except JobNotFoundError:
        return ApiResponse.error(message="Job not found", code=404)
    except JobNotCompletedError:
        return ApiResponse.error(message="Job is not completed yet", code=409)

    return ApiResponse.success(message="Download links generated", data=data)


@router.get("/recent-jobs")
async def get_recent_jobs(
    db_session: DbSessionDep,
    current_user: CurrentUserDep,
    limit: int = Query(default=10, ge=1, le=40),
):
    try:
        user_id = UUID(current_user.get("user_id"))
    except (TypeError, ValueError):
        return ApiResponse.error(message="Invalid id format", code=422)

    data = await JobService.get_recent_jobs(
        user_id=user_id, db_session=db_session, limit=limit
    )

    return ApiResponse.success(message="Recent jobs fetched Successfully", data=data)
