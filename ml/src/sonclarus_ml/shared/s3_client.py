import logging
from pathlib import Path

import aioboto3
from aiobotocore.config import AioConfig

from sonclarus_ml.shared.config import get_settings

logger = logging.getLogger(__name__)

settings = get_settings()

boto_session = aioboto3.Session(
    aws_access_key_id=settings.aws.access_key_id,
    aws_secret_access_key=settings.aws.secret_access_key.get_secret_value(),
    region_name=settings.aws.region,
)


def _s3_client():
    """Use AWS S3 or a self-hosted S3 endpoint from the shared settings."""
    endpoint = settings.aws.endpoint_url
    if endpoint:
        return boto_session.client(
            "s3",
            endpoint_url=endpoint,
            config=AioConfig(
                signature_version="s3v4",
                s3={"addressing_style": "path"},
            ),
        )
    return boto_session.client("s3")


class S3Client:
    """Async ML artifact transfers using the backend's S3 session settings."""

    async def download_file(
        self, s3_key: str, local_path: str, bucket_name: str | None = None
    ) -> None:
        """Download an object from S3 to a local path."""
        bucket = bucket_name or settings.aws.bucket_name
        Path(local_path).parent.mkdir(parents=True, exist_ok=True)
        async with _s3_client() as s3_client:
            try:
                logger.info("Downloading S3 key: %s", s3_key)
                await s3_client.download_file(bucket, s3_key, local_path)
            except Exception:
                logger.exception("S3 download failed for %s", s3_key)
                raise

    async def upload_file(
        self, local_path: str, s3_key: str, bucket_name: str | None = None
    ) -> None:
        """Upload a local file to S3."""
        bucket = bucket_name or settings.aws.bucket_name
        async with _s3_client() as s3_client:
            try:
                logger.info("Uploading to S3 key: %s", s3_key)
                await s3_client.upload_file(local_path, bucket, s3_key)
            except Exception:
                logger.exception("S3 upload failed for %s", s3_key)
                raise
