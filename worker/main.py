from arq.connections import RedisSettings
from app.config import settings
from worker.tasks import process_audios_pipeline


class WorkerSettings:
    """
    this is the logic for our arq worker
    arq looks at this class to know how to boot up
    """

    # connect to exact redis that our fastapi uses
    redis_settings = RedisSettings.from_dsn(settings.REDIS_URL)

    functions = [process_audios_pipeline]

    max_jobs = 1
    # process only 1 task at a time

    job_timeout = 3600  # 3600 seconds = 1 hour
