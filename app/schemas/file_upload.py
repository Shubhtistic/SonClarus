# schemas so we can upload an file and validate is using pydantic

from pydantic import BaseModel


class FileUpload(BaseModel):
    job_id: str
    status: str
    filename: str
    message: str
