import logging
from uuid import UUID, uuid7
from sqlalchemy.ext.asyncio import AsyncSession

from src.sonclarus.shared.kafka_client import KafkaProducer
from src.sonclarus.users.repository import UserRepository
from src.sonclarus.shared.config import get_settings
from src.sonclarus.shared.s3_client import (
    generate_presigned_post,
    verify_s3_upload,
    delete_file_from_s3,
)

from .models import Job
from .enums import JobStatus, StageName
from .schemas import STAGE_MODELS, DenoiseJob, FileMetadataDict, UploadRequestSchema
from .repository import JobRepository
from .exceptions import (
    InsufficientStorageError,
    JobNotFoundError,
    JobNotQueuedError,
    UploadNotFoundOnS3Error,
    ActualSizeExceedsStorageError,
)

logger = logging.getLogger(__name__)


class JobService:
    @staticmethod
    async def request_upload(
        db_session: AsyncSession,
        user_id: UUID,
        storage_limit: int,
        storage_used: int,
        payload: UploadRequestSchema,
    ) -> dict:

        settings = get_settings()

        remaining = storage_limit - storage_used
        if payload.file_size_bytes > remaining:
            raise InsufficientStorageError(remaining_bytes=remaining)

        job_id = uuid7()
        job_id_str = str(job_id)
        user_id_str = str(user_id)

        max_allowed_bytes = min(remaining, settings.file.max_file_size)

        object_key = f"{user_id_str}/{job_id_str}/original/{payload.filename}"

        presigned_data = await generate_presigned_post(
            max_allowed_bytes=max_allowed_bytes,
            object_key=object_key,
            expires_in=settings.app.upload_url_ttl_seconds,
        )

        original_file_metadata = FileMetadataDict(
            original_filename=payload.filename,
            content_type=payload.content_type,
            declared_size_bytes=payload.file_size_bytes,
            s3_bucket=settings.aws.bucket_name,
            s3_key=f"{user_id_str}/{job_id_str}/original",
        ).to_db()

        new_job = Job(
            id=job_id,
            user_id=user_id,
            selected_options=payload.selected_options,
            file_metadata=original_file_metadata,
        )

        await JobRepository.create_job(db_session=db_session, instance=new_job)

        logger.info("Upload requested: job_id=%s user_id=%s", job_id_str, user_id_str)

        return {"job_id": job_id_str, "presigned_post": presigned_data}

    @staticmethod
    async def confirm_upload(
        db_session: AsyncSession,
        user_id: UUID,
        storage_limit: int,
        storage_used: int,
        job_id: UUID,
    ) -> dict:

        user_id_str = str(user_id)
        job_id_str = str(job_id)

        job = await JobRepository.get_job_for_user(
            db_session=db_session, job_id=job_id, user_id=user_id
        )

        if job is None:
            raise JobNotFoundError(job_id=job_id_str)

        if job.status != JobStatus.PENDING_UPLOAD:
            raise JobNotQueuedError(job_id=job_id_str)

        orginal_file = FileMetadataDict.from_db(job.file_metadata)

        # object key
        object_key = (
            f"{user_id_str}/{job_id_str}/original/{orginal_file.original_filename}"
        )

        s3_result = await verify_s3_upload(object_key)

        if not s3_result["is_uploaded"]:
            await JobRepository.delete_job(
                db_session=db_session, job_id=job_id, user_id=user_id
            )
            raise UploadNotFoundOnS3Error(job_id=job_id_str)

        actual_size = s3_result["size"]
        last_modified = s3_result["last_modified"]

        if actual_size + storage_used > storage_limit:

            await JobRepository.delete_job(
                db_session=db_session, job_id=job_id, user_id=user_id
            )

            object_key = (
                f"{user_id_str}/{job_id_str}/original/{orginal_file.original_filename}"
            )

            await delete_file_from_s3(object_key)

            raise ActualSizeExceedsStorageError(job_id=job_id_str)

        # update the fields
        orginal_file.actual_size_bytes = actual_size
        orginal_file.charged_bytes = actual_size

        orginal_file_metadata = FileMetadataDict.model_validate(orginal_file).to_db()

        # check what selected options are in this job and add pending to all

        # denoise always runs; selected_options never contains it
        stage_names = [StageName.DENOISE] + [
            StageName(option.value) for option in job.selected_options
        ]

        stages = {
            name.value: STAGE_MODELS[name](
                s3_bucket=orginal_file.s3_bucket,
            ).model_dump(mode="json")
            for name in stage_names
        }

        confirmed = await JobRepository.confirm_job_and_update(
            db_session=db_session,
            job_id=job_id,
            user_id=user_id,
            file_metadata=orginal_file_metadata,
            stages=stages,
            uploaded_at=last_modified,
        )

        if not confirmed:
            raise JobNotQueuedError(job_id=job_id_str)

        charged = await UserRepository.increment_user_storage(
            db_session=db_session, user_id=user_id, delta_bytes=actual_size
        )

        if not charged:
            await db_session.rollback()  # undo the QUEUED update
            await JobRepository.delete_job(
                db_session=db_session, job_id=job_id, user_id=user_id
            )
            await delete_file_from_s3(object_key)
            raise ActualSizeExceedsStorageError(job_id=job_id_str)

        # after rollback, session starts new txn, so delete runs with that and at end dependancy commits it after router function finishes

        # commit before publishing, so workers never get a message for a job that isn't saved
        await db_session.commit()

        # publish to kafka
        data = DenoiseJob(
            job_id=job_id,
            user_id=user_id,
            s3_bucket=orginal_file.s3_bucket,
            s3_key=orginal_file.s3_key,
            requested_stage=StageName.DENOISE,
            input_filename=orginal_file.original_filename,
        ).model_dump(mode="json")

        denoise_topic = (get_settings()).kafka.denoise_topic

        await KafkaProducer.send_job(data, denoise_topic)

        logger.info("Upload confirmed: job_id=%s size=%d", job_id_str, actual_size)

        return {
            "message": "Upload confirmed and processing enqueued.",
            "job_id": job_id_str,
            "status": JobStatus.QUEUED,
        }
