from copy import deepcopy
import logging
from pathlib import PurePosixPath
from uuid import UUID, uuid7
from sqlalchemy.ext.asyncio import AsyncSession

from src.sonclarus.shared.kafka_client import KafkaProducer
from src.sonclarus.users.repository import UserRepository
from src.sonclarus.shared.config import get_settings
from src.sonclarus.shared.s3_client import (
    generate_presigned_get,
    generate_presigned_post,
    verify_s3_upload,
    delete_file_from_s3,
)

from .models import Job
from .enums import JobStatus, StageName, StageStatus
from .schemas import (
    STAGE_MODELS,
    JOB_MODELS,
    FileMetadataDict,
    DownloadLinksResponse,
    MlStageResultEvent,
    UploadRequestSchema,
    load_stage,
)
from .repository import JobRepository
from .exceptions import (
    InsufficientStorageError,
    JobNotCompletedError,
    JobNotFoundError,
    JobNotQueuedError,
    UploadNotFoundOnS3Error,
    ActualSizeExceedsStorageError,
)

logger = logging.getLogger(__name__)


class JobService:
    @staticmethod
    def _object_key(s3_key: str, filename: str) -> str:
        """Use a stored object key directly or append a filename to its prefix."""
        key = PurePosixPath(s3_key)
        if key.name == filename:
            return str(key)
        return str(key / filename)

    @staticmethod
    async def get_download_links(
        db_session: AsyncSession, user_id: UUID, job_id: UUID
    ) -> dict:
        """Return dashboard metadata and short-lived links for a completed job."""
        try:
            cached_data = await JobRepository.get_cached_download_links(
                user_id=user_id, job_id=job_id
            )
        except Exception:
            logger.exception("Could not read cached download links (job_id=%s)", job_id)
            cached_data = None
        if cached_data:
            try:
                return DownloadLinksResponse.model_validate(cached_data).model_dump(
                    mode="json"
                )
            except Exception:
                logger.exception(
                    "Cached download links failed validation (job_id=%s)", job_id
                )

        job = await JobRepository.get_job_for_user(
            db_session=db_session,
            job_id=job_id,
            user_id=user_id,
        )
        if job is None:
            raise JobNotFoundError(str(job_id))
        if not job.completed:
            raise JobNotCompletedError(str(job_id))

        settings = get_settings()
        original = FileMetadataDict.from_db(deepcopy(job.file_metadata))
        original_key = JobService._object_key(
            original.s3_key, original.original_filename
        )
        original_url = await generate_presigned_get(
            object_key=original_key,
            bucket_name=original.s3_bucket,
            expires_in=settings.app.download_url_ttl_seconds,
            filename=original.original_filename,
        )
        original_item = {
            "stage": "original",
            "filename": original.original_filename,
            "size_bytes": original.actual_size_bytes or original.declared_size_bytes,
            "content_type": original.content_type,
            "download_url": original_url,
        }

        files = [original_item]
        for stage_name, raw_stage in (job.stages or {}).items():
            stage_data = raw_stage or {}
            filenames = (
                [
                    stage_data.get("first_filename"),
                    stage_data.get("second_filename"),
                ]
                if stage_name == StageName.SEPARATE.value
                else [stage_data.get("filename")]
            )
            stage_bucket = stage_data.get("s3_bucket")
            stage_key = stage_data.get("s3_key")
            for filename in filenames:
                if not filename or not stage_bucket or not stage_key:
                    continue
                object_key = JobService._object_key(stage_key, filename)
                download_url = await generate_presigned_get(
                    object_key=object_key,
                    bucket_name=stage_bucket,
                    expires_in=settings.app.download_url_ttl_seconds,
                    filename=filename,
                )
                file_data = {
                    "stage": stage_name,
                    "filename": filename,
                    "size_bytes": (
                        stage_data.get("size_bytes")
                        if stage_name != StageName.SEPARATE.value
                        else None
                    ),
                    "content_type": stage_data.get("content_type"),
                    "download_url": download_url,
                }
                files.append(file_data)

        data = {
            "job": {
                "job_id": str(job.id),
                "status": job.status.value,
                "completed": job.completed,
                "current_stage": (
                    job.current_stage.value if job.current_stage is not None else None
                ),
                "selected_stages": [stage.value for stage in job.selected_options],
                "failed_stage": (
                    job.failed_stage.value if job.failed_stage is not None else None
                ),
                "created_at": job.created_at.isoformat(),
                "uploaded_at": job.uploaded_at.isoformat() if job.uploaded_at else None,
                "updated_at": job.updated_at.isoformat(),
                "completed_at": (
                    job.completed_at.isoformat() if job.completed_at else None
                ),
            },
            "files": files,
        }
        # Validate the dashboard payload and serialize datetimes/enums consistently
        # before it is returned or stored in Redis.
        data = DownloadLinksResponse.model_validate(data).model_dump(mode="json")

        try:
            await JobRepository.set_cached_download_links(
                user_id=user_id,
                job_id=job_id,
                data=data,
                ttl_seconds=settings.app.download_url_ttl_seconds,
            )
        except Exception:
            logger.exception("Could not cache download links (job_id=%s)", job_id)
        return data

    @staticmethod
    async def process_ml_result(
        db_session: AsyncSession, event: MlStageResultEvent
    ) -> bool:
        """Save one ML result and queue the next selected stage."""
        # Lock the row so two result messages cannot update this job at once.
        job = await JobRepository.get_job_for_ml_result(
            db_session=db_session,
            job_id=event.job_id,
            user_id=event.user_id,
        )
        if job is None:
            raise ValueError(
                f"No job found for ML result (job_id={event.job_id}, "
                f"user_id={event.user_id})"
            )

        # Copy JSON fields before editing them so the original values stay intact.
        stages = deepcopy(job.stages or {})
        existing_stage = stages.get(event.completed_stage.value, {})
        if existing_stage.get("status") == StageStatus.DONE.value:
            logger.info(
                "Ignoring duplicate ML result (job_id=%s stage=%s)",
                event.job_id,
                event.completed_stage.value,
            )
            return False

        if job.current_stage != event.completed_stage:
            raise ValueError(
                f"ML result stage {event.completed_stage.value!r} does not match "
                f"job current stage {job.current_stage!r} (job_id={event.job_id})"
            )

        selected_stages = [StageName(stage.value) for stage in job.selected_options]
        if event.completed_stage not in selected_stages:
            raise ValueError(
                f"ML result stage {event.completed_stage.value!r} was not selected "
                f"for job {event.job_id}"
            )
        is_first_stage = event.completed_stage == selected_stages[0]
        if event.is_initial != is_first_stage:
            raise ValueError(
                f"ML result initial flag does not match stage order "
                f"(job_id={event.job_id}, stage={event.completed_stage.value})"
            )

        stage_data = load_stage(event.completed_stage, event.stage_data)
        if stage_data.status != StageStatus.DONE:
            raise ValueError(
                f"ML result stage is not done (job_id={event.job_id}, "
                f"stage={event.completed_stage.value})"
            )
        if any(output.s3_bucket != stage_data.s3_bucket for output in event.outputs):
            raise ValueError(
                f"ML result bucket mismatch (job_id={event.job_id}, "
                f"stage={event.completed_stage.value})"
            )

        if event.is_initial:
            if event.file_hash is None:
                raise ValueError(
                    f"Initial ML result is missing file_hash (job_id={event.job_id})"
                )
            # The first stage sees the uploaded file, so it supplies the hash.
            file_metadata = deepcopy(job.file_metadata)
            original_file = FileMetadataDict.from_db(file_metadata)
            original_file.file_hash = event.file_hash
            file_metadata["original"] = original_file.model_dump(mode="json")
            job.file_metadata = file_metadata

        stages[event.completed_stage.value] = stage_data.model_dump(mode="json")
        job.stages = stages

        selected_index = selected_stages.index(event.completed_stage)
        next_stage = (
            selected_stages[selected_index + 1]
            if selected_index + 1 < len(selected_stages)
            else None
        )

        job.completed = next_stage is None
        job.status = JobStatus.COMPLETED if next_stage is None else JobStatus.PROCESSING
        job.completed_at = event.completed_at if next_stage is None else None
        job.current_stage = next_stage or event.completed_stage

        if next_stage is not None:
            next_job = JobService._build_next_stage_job(
                job_id=event.job_id,
                user_id=event.user_id,
                completed_stage=event.completed_stage,
                next_stage=next_stage,
                stage_data=stage_data.model_dump(mode="python"),
            )
            topic = JobService._stage_topic(next_stage)
            # Keep the database changes in this transaction if Kafka send fails.
            await db_session.flush()
            await KafkaProducer.send_job(next_job, topic)

        logger.info(
            "ML result applied (job_id=%s completed_stage=%s next_stage=%s)",
            event.job_id,
            event.completed_stage.value,
            next_stage.value if next_stage else None,
        )
        return True

    @staticmethod
    def _stage_topic(stage: StageName) -> str:
        settings = get_settings()
        return {
            StageName.DENOISE: settings.kafka.denoise_topic,
            StageName.SEPARATE: settings.kafka.separate_topic,
            StageName.TRANSCRIBE: settings.kafka.transcribe_topic,
            StageName.SUMMARIZE: settings.kafka.summarize_topic,
        }[stage]

    @staticmethod
    def _build_next_stage_job(
        job_id: UUID,
        user_id: UUID,
        completed_stage: StageName,
        next_stage: StageName,
        stage_data: dict,
    ) -> dict:
        s3_bucket = stage_data.get("s3_bucket")
        s3_key = stage_data.get("s3_key")
        if not s3_bucket or not s3_key:
            raise ValueError(
                f"Completed stage is missing S3 location "
                f"(stage={completed_stage.value})"
            )

        common = {
            "job_id": job_id,
            "user_id": user_id,
            "s3_bucket": s3_bucket,
            "s3_key": s3_key,
            "is_initial": False,
        }

        if next_stage == StageName.TRANSCRIBE:
            is_separated = completed_stage == StageName.SEPARATE
            if is_separated:
                message_fields = {
                    "is_seperated": True,
                    "input_filename1": stage_data.get("first_filename"),
                    "input_filename2": stage_data.get("second_filename"),
                }
            else:
                message_fields = {
                    "is_seperated": False,
                    "input_filename": stage_data.get("filename"),
                }
        else:
            message_fields = {"input_filename": stage_data.get("filename")}

        message = JOB_MODELS[next_stage](**common, **message_fields)
        return message.model_dump(mode="json")

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
        stage_names = [StageName(option.value) for option in job.selected_options]

        # first stage to publish, read now because job attributes expire after the commit below
        first_stage = stage_names[0]

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
            current_stage=first_stage,
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
        # transcribe also needs is_seperated, False here because separate would have been the first stage otherwise
        extra_fields = (
            {"is_seperated": False} if first_stage == StageName.TRANSCRIBE else {}
        )

        # the first selected stage always reads the original upload
        data = JOB_MODELS[first_stage](
            job_id=job_id,
            user_id=user_id,
            s3_bucket=orginal_file.s3_bucket,
            s3_key=orginal_file.s3_key,
            requested_stage=first_stage,
            input_filename=orginal_file.original_filename,
            is_initial=True,
            **extra_fields,
        ).model_dump(mode="json")

        if first_stage == StageName.DENOISE:
            first_stage_topic = (get_settings()).kafka.denoise_topic
        elif first_stage == StageName.SEPARATE:
            first_stage_topic = (get_settings()).kafka.separate_topic
        elif first_stage == StageName.TRANSCRIBE:
            first_stage_topic = (get_settings()).kafka.transcribe_topic
        elif first_stage == StageName.SUMMARIZE:
            first_stage_topic = (get_settings()).kafka.summarize_topic

        await KafkaProducer.send_job(data, first_stage_topic)

        logger.info("Upload confirmed: job_id=%s size=%d", job_id_str, actual_size)

        return {
            "message": "Upload confirmed and processing enqueued.",
            "job_id": job_id_str,
            "status": JobStatus.QUEUED,
        }
