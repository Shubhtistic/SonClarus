import asyncio
from sqlalchemy import select, update
from app.db.database_session import AsyncSessionLocal
from app.db.db_models import Job, JobStatus
from worker.s3_service import S3Service
from worker.s3_utils import setup_job_workspace, cleanup_job_workspace


async def process_audios_pipeline(ctx: dict, job_id: str):
    s3 = S3Service()
    job_dir = setup_job_workspace(job_id)

    try:
        # 1. FETCH JOB & UPDATE STATUS
        async with AsyncSessionLocal() as session:
            job = (
                await session.execute(select(Job).where(Job.id == job_id))
            ).scalar_one_or_none()
            if not job:
                return False

            await session.execute(
                update(Job).where(Job.id == job_id).values(status=JobStatus.PROCESSING)
            )
            await session.commit()

        user_id = str(job.user_id)
        # S3 logic assumes file is at: user_id/job_id/original/filename
        s3_key = f"{user_id}/{job_id}/original/{job.filename}"
        local_og_path = job_dir / "original" / job.filename

        # 2. DOWNLOAD ORIGINAL
        await s3.download_file(s3_key, str(local_og_path))
        current_file = str(local_og_path)

        # 3. [PLACEHOLDER] DENOISE
        if job.is_denoise:
            print("--- Running DeepFilterNet ---")
            # TODO: current_file = await run_denoise(current_file, job_dir / "denoise")
            pass

        # 4. [PLACEHOLDER] SEPARATION
        if job.is_separation:
            print("--- Running SepFormer ---")
            # TODO: await run_separation(current_file, job_dir / "separated")
            await s3.upload_folder(
                str(job_dir / "separated"), user_id, job_id, "separated"
            )

        # 5. [PLACEHOLDER] TRANSCRIPTION & SUMMARY
        if job.is_transcription:
            print("--- Running Whisper ---")
            # TODO: summary = await run_transcription(current_file, job_dir / "transcribe")
            await s3.upload_folder(
                str(job_dir / "transcribe"), user_id, job_id, "transcribe"
            )

            # Update DB with summary
            # async with AsyncSessionLocal() as session:
            #     await session.execute(update(Job).where(Job.id == job_id).values(summary=summary))
            #     await session.commit()

        # 6. MARK COMPLETE
        async with AsyncSessionLocal() as session:
            await session.execute(
                update(Job).where(Job.id == job_id).values(status=JobStatus.COMPLETED)
            )
            await session.commit()

    except Exception as e:
        print(f"❌ Pipeline Error: {e}")
        async with AsyncSessionLocal() as session:
            await session.execute(
                update(Job).where(Job.id == job_id).values(status=JobStatus.FAILED)
            )
            await session.commit()

    finally:
        cleanup_job_workspace(job_id)

    return True
