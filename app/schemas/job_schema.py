from pydantic import BaseModel


class UploadRequest(BaseModel):
    filename: str
    file_size_bytes: int
