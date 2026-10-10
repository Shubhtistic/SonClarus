class InsufficientStorageError(Exception):
    """raised when user does not have enough storage for the declared size"""

    def __init__(self, remaining_bytes: int):
        self.remaining_bytes = remaining_bytes


class JobNotFoundError(Exception):
    """raised when a job row is not found for the given user"""

    def __init__(self, job_id: str):
        self.job_id = job_id


class JobNotQueuedError(Exception):
    """raised when a job is not in PENDING_UPLOAD state at confirm time"""

    def __init__(self, job_id: str):
        self.job_id = job_id


class UploadNotFoundOnS3Error(Exception):
    """raised when the file is not present on S3 after client claims to have uploaded"""

    def __init__(self, job_id: str):
        self.job_id = job_id


class ActualSizeExceedsStorageError(Exception):
    """raised when the real file size on S3 would overflow the user's storage quota"""

    def __init__(self, job_id: str):
        self.job_id = job_id
