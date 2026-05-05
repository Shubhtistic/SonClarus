import asyncio
import importlib
import multiprocessing as mp
from pathlib import Path
from sqlalchemy import select, update

from app.db.database_session import AsyncSessionLocal
from app.db.db_models import Job, JobStatus

from worker.s3_service import S3Service
from worker.s3_utils import setup_job_workspace, cleanup_job_workspace


def _isolated_worker(module_name, func_name, queue, args):
    try:
        module = importlib.import_module(module_name)
        func = getattr(module, func_name)
        result = func(*args)
        queue.put({"status": "success", "data": result})
    except Exception as e:
        queue.put({"status": "error", "data": str(e)})


def run_isolated(module_name, func_name, *args):
    ctx = mp.get_context("spawn")
    queue = ctx.Queue()
    p = ctx.Process(target=_isolated_worker, args=(module_name, func_name, queue, args))

    p.start()
    p.join()  # the os will terminate the process here and free up vram

    if p.exitcode != 0:
        raise RuntimeError(f"ML Stage {func_name} crashed, Exit code: {p.exitcode}")

    if not queue.empty():
        res = queue.get()
        if res["status"] == "error":
            raise RuntimeError(res["data"])
        return res["data"]

    raise RuntimeError(f"ML Stage {func_name} exited cleanly but returned no data.")


async def process_audios_pipeline(ctx: dict, job_id: str):
    s3 = S3Service()
    job_dir = setup_job_workspace(job_id)
    final_script_text = ""

    try:
        # fetch db
        async with AsyncSessionLocal() as session:
            job = (
                await session.execute(select(Job).where(Job.id == job_id))
            ).scalar_one_or_none()
            if not job:
                print(f"Job {job_id} not found.")
                return False

        user_id = str(job.user_id)
        # object_key -> stored as 'user_id/job_id/original/file.wav'
        local_og_path = job_dir / "original" / job.filename

        # download from s3
        await s3.download_file(job.object_key, str(local_og_path))
        # current file is the original audio
        current_file = str(local_og_path)

        # denoise
        if job.is_denoise:
            print("Stage: Denoising ...")
            async with AsyncSessionLocal() as session:
                await session.execute(
                    update(Job)
                    .where(Job.id == job_id)
                    .values(status=JobStatus.DENOISING)
                )
                await session.commit()

            denoise_folder = job_dir / "denoise"

            current_file = await asyncio.to_thread(
                run_isolated,
                "worker.ml_models.denoise",
                "run_denoise",
                current_file,
                denoise_folder,
            )

        # seperation
        if job.is_separation:
            print("Stage: seperation...")
            async with AsyncSessionLocal() as session:
                await session.execute(
                    update(Job)
                    .where(Job.id == job_id)
                    .values(status=JobStatus.SEPARATING)
                )
                await session.commit()

            separated_folder = job_dir / "separated"

            active_files = await asyncio.to_thread(
                run_isolated,
                "worker.ml_models.separate",
                "run_separation",
                current_file,
                separated_folder,
            )

            # upload to s3
            await s3.upload_folder(str(separated_folder), user_id, job_id, "separated")
        else:
            active_files = [current_file]

        # transcribe
        if job.is_transcription:
            print("Stage: Transcribing ...")
            async with AsyncSessionLocal() as session:
                await session.execute(
                    update(Job)
                    .where(Job.id == job_id)
                    .values(status=JobStatus.TRANSCRIBING)
                )
                await session.commit()

            all_dialogue_segments = []

            for index, file_path in enumerate(active_files):
                speaker_label = f"Speaker {index + 1}"

                speaker_segments = await asyncio.to_thread(
                    run_isolated,
                    "worker.ml_models.transcribe",
                    "run_transcription",
                    file_path,
                    speaker_label,
                )
                all_dialogue_segments.extend(speaker_segments)

            all_dialogue_segments.sort(key=lambda x: x["start"])

            final_script_text = "".join(
                [
                    f"[{s['start']:.2f} -> {s['end']:.2f}] {s['speaker']}: {s['text']}\n"
                    for s in all_dialogue_segments
                ]
            )

            # Save locally then upload to S3
            base_name = Path(job.filename).stem
            transcript_path = job_dir / "transcribe" / f"{base_name}_full_script.txt"
            transcript_path.parent.mkdir(parents=True, exist_ok=True)
            with open(transcript_path, "w", encoding="utf-8") as f:
                f.write(final_script_text)

            await s3.upload_folder(
                str(job_dir / "transcribe"), user_id, job_id, "transcribe"
            )

            # summarize
            if final_script_text.strip():
                print("✨ Stage: Summarizing...")
                async with AsyncSessionLocal() as session:
                    await session.execute(
                        update(Job)
                        .where(Job.id == job_id)
                        .values(status=JobStatus.SUMMARIZING)
                    )
                    await session.commit()

                ai_summary = await asyncio.to_thread(
                    run_isolated,
                    "worker.ml_models.summarize",
                    "run_summarization",
                    final_script_text,
                )

                # update db with summary
                async with AsyncSessionLocal() as session:
                    await session.execute(
                        update(Job).where(Job.id == job_id).values(summary=ai_summary)
                    )
                    await session.commit()

        # final step
        async with AsyncSessionLocal() as session:
            await session.execute(
                update(Job).where(Job.id == job_id).values(status=JobStatus.DONE)
            )
            await session.commit()
        print(f"Job {job_id} completed.")

    except Exception as e:
        print(f"Worker Failed: {e}")
        # record error in db for that job id
        async with AsyncSessionLocal() as session:
            await session.execute(
                update(Job)
                .where(Job.id == job_id)
                .values(status=JobStatus.FAILED, error_message=str(e))
            )
            await session.commit()
    finally:
        # clear the whole job after completion
        cleanup_job_workspace(job_id)

    return True
