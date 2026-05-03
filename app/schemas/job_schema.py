from pydantic import BaseModel
from typing import List, Optional
from uuid import UUID


class UploadRequest(BaseModel):
    filename: str


class UploadResponse(BaseModel):
    job_id: UUID
    presigned_post: dict


class TranscriptLine(BaseModel):
    speaker: str
    text: str


class JobResult(BaseModel):
    status: str
    transcript: Optional[List[TranscriptLine]] = None
    summary: Optional[str] = None
    action_items: Optional[List[str]] = None
