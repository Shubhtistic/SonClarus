import logging
from urllib.parse import quote

import aioboto3
from botocore.exceptions import ClientError
from fastapi import HTTPException, status
from aiobotocore.config import AioConfig

from src.sonclarus.shared.config import get_settings

logger = logging.getLogger(__name__)


settings = get_settings()

boto_session = aioboto3.Session(
    aws_access_key_id=settings.aws.access_key_id,
    aws_secret_access_key=settings.aws.secret_access_key.get_secret_value(),
    region_name=settings.aws.region,
)


def _s3_client():
    """Real AWS when no endpoint is set, otherwise a self-hosted S3 (RustFS)."""
    endpoint = settings.aws.endpoint_url
    if endpoint:
        return boto_session.client(
            "s3",
            endpoint_url=endpoint,
            # during local we use our rustfs link, overrides the default, example -> https://s3.ap-south-1.amazonaws.com
            config=AioConfig(
                signature_version="s3v4",
                s3={"addressing_style": "path"},
            ),
            # request signing algo, aws has it as default, but for custom fs this makes sure they get there required
            # addressing_style -> this controls how the bucket appears in the URL
        )
    return boto_session.client("s3")


def _s3_presign_client():
    """Sign browser-facing links with the public endpoint when configured."""
    endpoint = settings.aws.public_endpoint_url or settings.aws.endpoint_url
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


async def generate_presigned_get(
    object_key: str,
    bucket_name: str | None = None,
    expires_in: int = 600,
    filename: str | None = None,
) -> str:
    """Create a short-lived download URL for an exact S3 object."""

    async with _s3_presign_client() as s3_client:
        try:
            params = {
                "Bucket": bucket_name or settings.aws.bucket_name,
                "Key": object_key,
            }
            if filename:
                params["ResponseContentDisposition"] = (
                    f"attachment; filename*=UTF-8''{quote(filename)}"
                )
            response = await s3_client.generate_presigned_url(
                ClientMethod="get_object",
                Params=params,
                ExpiresIn=expires_in,
            )
            return response
        except Exception:
            logger.exception("Failed to generate presigned GET url for %s", object_key)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Could not generate download url",
            )


async def generate_presigned_post(
    max_allowed_bytes: int,
    object_key: str,
    expires_in: int = 600,
) -> dict:
    """a secure url for frontend to upload file to s3"""

    async with _s3_presign_client() as s3_client:
        try:
            response = await s3_client.generate_presigned_post(
                Bucket=settings.aws.bucket_name,
                Key=object_key,
                Fields={"Content-Type": "audio/wav"},
                Conditions=[
                    {"Content-Type": "audio/wav"},
                    ["content-length-range", 1024, max_allowed_bytes],
                ],
                ExpiresIn=expires_in,
            )
            return response
        except Exception:
            logger.exception("Failed to generate presigned POST url for %s", object_key)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Could not generate upload url",
            )


async def verify_s3_upload(object_key: str) -> dict:
    """Checks if file is uploaded to s3 or not"""

    async with _s3_client() as s3_client:
        try:
            response = await s3_client.head_object(
                Bucket=settings.aws.bucket_name, Key=object_key
            )
            return {
                "is_uploaded": True,
                "size": response["ContentLength"],
                "last_modified": response["LastModified"],
            }
        except ClientError as e:
            if e.response["Error"]["Code"] in ("404", "NoSuchKey"):
                return {"is_uploaded": False, "size": 0, "last_modified": None}
            logger.exception("S3 ClientError on head_object for %s", object_key)
            raise


async def delete_file_from_s3(object_key: str) -> None:
    """Delete the exact uploaded file"""

    async with _s3_client() as s3_client:
        try:
            await s3_client.delete_object(
                Bucket=settings.aws.bucket_name, Key=object_key
            )
        except Exception:
            logger.exception("S3 delete failed for %s", object_key)
