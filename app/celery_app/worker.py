from app.db.db_models import Job, JobArtifact, ArtifactType, JobStatus

from app.celery_app.forensics.utils import compute_sha256, get_audio_metadata
from app.celery_app.forensics.analyzer import (
    generate_waveform_image,
    generate_spectrogram_image,
)
from app.celery_app.forensics.report import generate_pdf_report


import os
from app.config import settings
from sqlmodel import create_engine, Session
from celery import Celery

sync_db_url = settings.POSTGRES_URL.replace("+asyncpg", "")

engine = create_engine(sync_db_url)

celery_app = Celery("worker", broker=settings.REDIS_URL, backend=settings.REDIS_URL)


@celery_app.task(name="process_forensics")
def process_forensics(job_id: str):
    print(f"starting background analysis for {job_id}")

    # Open a standard blocking session
    with Session(engine) as session:
        # lets find the job
        job = session.get(Job, job_id)

        if not job:
            print(f"No such job {job_id}")
            return "Job Not Found"

        # B. Mark as PROCESSING
        job.status = JobStatus.PROCESSING
        session.add(job)
        session.commit()
        session.refresh(job)

        # once we found the job_id
        # we find the saved filepah
        # once we know its location we can easily do operations on it
        try:
            source_path = job.filepath

            job_folder = os.path.dirname(source_path)

            # results will be saved in these paths
            waveform_path = os.path.join(job_folder, "waveform.png")
            spectrogram_path = os.path.join(job_folder, "spectrogram.png")
            report_path = os.path.join(job_folder, "forensic_report.pdf")

            # run the tools
            print(" Calculating hash and metadata.......")
            file_hash = compute_sha256(source_path)
            metadata = get_audio_metadata(source_path)

            print("Generating Visuals .....")
            generate_waveform_image(source_path, waveform_path)
            generate_spectrogram_image(source_path, spectrogram_path)

            print(" building pdf report ....")
            generate_pdf_report(
                metadata, file_hash, waveform_path, spectrogram_path, report_path
            )

            # save to
            print("saving to DB .....")

            # Create the Artifact entry for the PDF Report
            pdf_artifact = JobArtifact(
                job_id=job.id,
                type=ArtifactType.REPORT,
                label="Forensic Analysis PDF",
                file_path=report_path,
                file_hash=file_hash,
            )
            session.add(pdf_artifact)

            job.status = JobStatus.COMPLETED
            session.add(job)
            session.commit()

            print(f"SUCCESS: Job {job_id} completed")
            return "Success"

        except Exception as e:
            # if anything crashes mark as failed
            print(f"CRITICAL FAILURE: {str(e)}")
            job.status = JobStatus.FAILED
            session.add(job)
            session.commit()
            return f"Failed: {str(e)}"
