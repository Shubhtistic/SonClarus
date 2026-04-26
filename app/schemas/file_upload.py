from pydantic import BaseModel


class UploadRequest(BaseModel):
    filename: str
    is_denoise: bool = False
    is_separation: bool = False
    is_transcription: bool = False
