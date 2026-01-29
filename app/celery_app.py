from celery import Celery
from app.config import settings
import time

celery_worker = Celery(
    "Sonclarus celery app", broker=settings.REDIS_URL, backend=settings.REDIS_URL
)


@celery_worker.task(name="process_audio_file")
def process_audio_file(job_id: str, file_path: str):
    """This mimics an ai task , we will later modify it once we start doing ml work"""
    print(f"Started processing job: {job_id}")

    # Mimic heavy work (AI Loading...)
    time.sleep(5)

    print(f"Finished processing job: {job_id}")

    return {"status": "COMPLETED", "job_id": job_id}
