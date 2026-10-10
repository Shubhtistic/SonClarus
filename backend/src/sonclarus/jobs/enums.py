from enum import Enum


class SelectedStages(str, Enum):
    SEPARATE = "separate"  # user choice
    TRANSCRIBE = "transcribe"  # user choice
    SUMMARIZE = "summarize"  # user choice, requires transcribe


class JobStatus(str, Enum):
    """Lifecycle of the whole job."""

    PENDING_UPLOAD = "PENDING_UPLOAD"  # row created, waiting for client -> S3 upload
    QUEUED = "QUEUED"  # upload confirmed, to be published to Kafka
    PROCESSING = "PROCESSING"  # ML project has picked it up
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    EXPIRED = "EXPIRED"  # upload never confirmed in time
    CANCELLED = "CANCELLED"


class StageName(str, Enum):
    DENOISE = "denoise"
    SEPARATE = "separate"
    TRANSCRIBE = "transcribe"
    SUMMARIZE = "summarize"


class StageStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"
    SKIPPED = "skipped"
