# schemas so we can upload an file and validate is using pydantic

from pydantic import BaseModel


class UploadRequest(BaseModel):
    filename: str
