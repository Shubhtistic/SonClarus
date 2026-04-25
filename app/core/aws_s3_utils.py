import aioboto3
from fastapi import HTTPException, status
from app.config import settings

# create a global session
# so fastapi does not open new session for every user

boto_session = aioboto3.Session(
    aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
    aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
    region_name=settings.AWS_REGION,
)


async def generate_presigned_post(user_id: str, job_id: str, filename: str) -> dict:
    """a secure url for frontend to upload file to s3"""

    object_key = f"{user_id}/{job_id}/original/{filename}"

    async with boto_session.client("s3") as s3_client:
        try:
            response = await s3_client.generate_presigned_post(
                Bucket=settings.AWS_BUCKET_NAME,
                Key=object_key,
                Fields={"Content-Type": "audio/wav"},
                Conditions=[
                    # must be wav file
                    {"Content-Type": "audio/wav"},
                    # mst be 1kb to 50mb
                    ["content-length-range", 1024, 52428800],
                ],
                ExpiresIn=1800,  # 30 mins
            )
            return response

        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Could no generate upload url",
            )


async def verify_s3_upload(user_id: str, job_id: str, filename: str) -> bool:
    "Checks if file is uploaded to s3 or not"

    object_key = f"{user_id}/{job_id}/original/{filename}"

    try:
        # head_objects only returns files metadata
        async with boto_session.client("s3") as s3_client:
            response = await s3_client.head_object(
                Bucket=settings.AWS_BUCKET_NAME, Key=object_key
            )

            return True
    except s3_client.exceptions.ClientError as e:
        # if 404  error -> file missing
        if e.response["Error"]["Code"] == "404":
            return False
        raise
