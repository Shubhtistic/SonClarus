import os
import aioboto3
from app.config import settings


class S3Service:
    def __init__(self):
        self.session = aioboto3.Session()
        self.bucket = settings.AWS_BUCKET_NAME
        self.creds = {
            "region_name": settings.AWS_REGION,
            "aws_access_key_id": settings.AWS_ACCESS_KEY_ID,
            "aws_secret_access_key": settings.AWS_SECRET_ACCESS_KEY,
        }

    async def download_file(self, s3_key: str, local_path: str):
        """Generic download: S3 Key -> Local Path"""
        async with self.session.client("s3", **self.creds) as s3:
            print(f"📥 [S3] Downloading: {s3_key}")
            await s3.download_file(self.bucket, s3_key, local_path)

    async def upload_folder(
        self, local_folder: str, user_id: str, job_id: str, phase_name: str
    ):
        """Uploads every file in a folder to: {user_id}/{job_id}/{phase_name}/filename"""
        if not os.path.exists(local_folder):
            return

        async with self.session.client("s3", **self.creds) as s3:
            for filename in os.listdir(local_folder):
                local_path = os.path.join(local_folder, filename)
                if os.path.isfile(local_path):
                    s3_key = f"{user_id}/{job_id}/{phase_name}/{filename}"
                    print(f"📤 [S3] Uploading {phase_name}: {filename}")
                    await s3.upload_file(local_path, self.bucket, s3_key)
