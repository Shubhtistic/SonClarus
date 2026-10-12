from datetime import datetime
import re
from typing import Any, Literal, Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .enums import JobStatus, SelectedStages, StageName, StageStatus
from src.sonclarus.shared.utilities import reject_blank_text


class UploadRequestSchema(BaseModel):
    filename: str = Field(min_length=1, max_length=255)
    file_size_bytes: int
    selected_options: list[SelectedStages]
    content_type: Literal["audio/wav"]

    _validate_text = field_validator("filename", mode="before")(reject_blank_text)

    @model_validator(mode="after")
    def validate_stage_dependencies(self) -> "UploadRequestSchema":
        # an empty list means nothing to run
        if not self.selected_options:
            raise ValueError("select at least one stage")
        if (
            SelectedStages.SUMMARIZE in self.selected_options
            and SelectedStages.TRANSCRIBE not in self.selected_options
        ):
            raise ValueError("summarize requires transcribe to be selected")

        # drop duplicates and store in pipeline order (enum member order)
        order = list(SelectedStages)
        self.selected_options = sorted(set(self.selected_options), key=order.index)
        return self

    @field_validator("filename")
    @classmethod
    def must_be_plain_wav_filename(cls, v: str) -> str:
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*\.wav", v):
            raise ValueError(
                "filename must be a plain .wav filename without spaces or paths"
            )
        return v

    @field_validator("file_size_bytes")
    @classmethod
    def must_be_positive(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("file_size_bytes must be positive")
        return v


# --- Job JSONB Schemas ---


class StageData(BaseModel):
    """Common base class for all stage dict schemas"""

    model_config = ConfigDict(extra="forbid")  # catches typos in field names

    status: StageStatus = StageStatus.PENDING
    s3_bucket: str
    s3_key: Optional[str] = None
    size_bytes: Optional[int] = None
    content_type: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error: Optional[str] = None


class Denoise(StageData):
    filename: Optional[str] = None


class Separate(StageData):
    first_filename: Optional[str] = None
    second_filename: Optional[str] = None


class Transcribe(StageData):
    filename: Optional[str] = None


class Summarize(StageData):
    filename: Optional[str] = None


STAGE_MODELS: dict[StageName, type[StageData]] = {
    StageName.DENOISE: Denoise,
    StageName.SEPARATE: Separate,
    StageName.TRANSCRIBE: Transcribe,
    StageName.SUMMARIZE: Summarize,
}


def load_stage(name: StageName, raw: dict[str, Any]) -> StageData:
    """validate a raw dict from the DB or Kafka against the right stage model"""
    return STAGE_MODELS[name].model_validate(raw)


# --- Original File dict ---


class FileMetadataDict(BaseModel):
    """The uploaded input file. Stored as {"original": {...}} in its own JSONB column"""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    original_filename: str = Field(max_length=255)
    content_type: str = Field(default="audio/wav", max_length=100)
    declared_size_bytes: int
    actual_size_bytes: Optional[int] = None  # from head_object on confirm

    s3_bucket: str = Field(max_length=63)
    s3_key: str = Field(max_length=1024)

    # sha256 as 64 lowercase hex chars
    file_hash: Optional[str] = Field(default=None, pattern=r"^[0-9a-f]{64}$")

    # exactly what was deducted from users.storage_used
    charged_bytes: int = 0

    def to_db(self) -> dict[str, Any]:
        """validated dict to save: {"original": {...}}"""
        return {"original": self.model_dump(mode="json")}

    @classmethod
    def from_db(cls, raw: dict[str, Any]) -> "FileMetadataDict":
        """validate the stored dict and return the model"""
        return cls.model_validate(raw["original"])


class DownloadFile(BaseModel):
    """Safe dashboard fields for one downloadable file."""

    stage: str
    filename: str
    size_bytes: Optional[int] = None
    content_type: Optional[str] = None
    download_url: str


class DownloadJobSummary(BaseModel):
    job_id: UUID
    status: JobStatus
    completed: bool
    current_stage: Optional[StageName] = None
    selected_stages: list[StageName]
    failed_stage: Optional[StageName] = None
    created_at: datetime
    uploaded_at: Optional[datetime] = None
    updated_at: datetime
    completed_at: Optional[datetime] = None


class DownloadLinksResponse(BaseModel):
    """Job summary and one flat list of safe, temporary file links."""

    job: DownloadJobSummary
    files: list[DownloadFile]


class RecentJobsResponse(BaseModel):
    id: UUID
    completed: bool
    status: JobStatus
    selected_options: list[SelectedStages]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ================================================================================================================================

# --- Kafka Schemas ----


class StageOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    filename: str = Field(min_length=1)
    s3_key: str = Field(min_length=1)
    size_bytes: int = Field(ge=0)
    content_type: str = Field(min_length=1)
    s3_bucket: str = Field(min_length=1)


class MlStageResultEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    job_id: UUID
    user_id: UUID
    completed_stage: StageName
    is_initial: bool
    file_hash: Optional[str] = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    stage_data: dict[str, Any]
    outputs: list[StageOutput] = Field(min_length=1)
    completed_at: datetime


class StageJobBase(BaseModel):
    """Common fields for every message the backend publishes to Kafka"""

    model_config = ConfigDict(extra="forbid")

    job_id: UUID
    user_id: UUID
    s3_bucket: str
    s3_key: str
    is_initial: bool


class DenoiseJob(StageJobBase):
    requested_stage: Literal[StageName.DENOISE] = StageName.DENOISE
    input_filename: str  # original file


class SeparateJob(StageJobBase):
    requested_stage: Literal[StageName.SEPARATE] = StageName.SEPARATE
    input_filename: str  # the denoised file


class TranscribeJob(StageJobBase):
    requested_stage: Literal[StageName.TRANSCRIBE] = StageName.TRANSCRIBE
    is_seperated: bool
    # the two transcribed files
    input_filename: Optional[str] = None
    input_filename1: Optional[str] = None
    input_filename2: Optional[str] = None

    @model_validator(mode="after")
    def validate_input_filenames(self) -> "TranscribeJob":
        if self.is_seperated:
            if not self.input_filename1 or not self.input_filename2:
                raise ValueError(
                    "separated transcription requires input_filename1 and input_filename2"
                )
            if self.input_filename:
                raise ValueError(
                    "separated transcription must not include input_filename"
                )
        else:
            if not self.input_filename:
                raise ValueError("non-separated transcription requires input_filename")
            if self.input_filename1 or self.input_filename2:
                raise ValueError(
                    "non-separated transcription must not include input_filename1 or input_filename2"
                )
        return self


class SummarizeJob(StageJobBase):
    requested_stage: Literal[StageName.SUMMARIZE] = StageName.SUMMARIZE
    input_filename: str  # the transcript


# stage -> message class, used to build the first message now and the next-stage ones later
JOB_MODELS: dict[StageName, type[StageJobBase]] = {
    StageName.DENOISE: DenoiseJob,
    StageName.SEPARATE: SeparateJob,
    StageName.TRANSCRIBE: TranscribeJob,
    StageName.SUMMARIZE: SummarizeJob,
}
