from datetime import datetime, timezone
from typing import Optional
from uuid import UUID, uuid7

from sqlalchemy import (
    ARRAY,
    Column,
    DateTime,
    text,
    Enum as SaEnum,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.mutable import MutableDict
from sqlmodel import Field, SQLModel

from .enums import JobStatus, SelectedStages, StageName

"""
Shape of one entry inside Job.stages (key = StageName value):
look at schemas.py for more info

Example:-

stages = {
  "denoise": {
      "status": "done",
      "s3_bucket": "sonclarus1",
      "s3_key": "<user>/<job>/denoise/clean.wav",
      "size_bytes": 1234567,
      "content_type": "audio/wav",
      "config": {},
      "started_at": "2026-10-05T10:00:00Z",
      "completed_at": "2026-10-05T10:00:40Z",
      "error": null,
      "filename": "clean.wav"
  },
  "separate": {
      "status": "pending",
      "s3_bucket": "sonclarus1",
      "s3_key": null,
      "size_bytes": null,
      "content_type": null,
      "config": {},
      "started_at": null,
      "completed_at": null,
      "error": null,
      "first_filename": null,
      "second_filename": null
  },
}
"""


class Job(SQLModel, table=True):
    __tablename__ = "jobs"

    id: UUID = Field(default_factory=uuid7, primary_key=True)

    # user fk
    user_id: UUID = Field(foreign_key="users.id", ondelete="RESTRICT", index=True)

    # for downloads, if thhis is true return a link
    completed: bool = Field(default=False)

    # job lifecycle
    status: JobStatus = Field(
        default=JobStatus.PENDING_UPLOAD,
        sa_column=Column(
            SaEnum(
                JobStatus,
                name="job_status_enum",
                native_enum=False,
                length=32,
                values_callable=lambda e: [m.value for m in e],
            ),
            nullable=False,
        ),
    )

    # which stage is running right now; for GET /status
    current_stage: Optional[StageName] = Field(
        default=None,
        sa_column=Column(
            SaEnum(
                StageName,
                name="stage_name_enum",
                native_enum=False,
                length=32,
                values_callable=lambda e: [m.value for m in e],
            ),
            nullable=True,
        ),
    )

    # What the user asked for. Only user-facing choices, e.g. ["separate", "transcribe"].
    # Denoise never appears here. Set once at request time.
    selected_options: list[SelectedStages] = Field(
        default_factory=list,
        sa_column=Column(
            ARRAY(
                SaEnum(
                    SelectedStages,
                    name="selected_stage_enum",
                    native_enum=False,
                    length=32,
                    values_callable=lambda e: [m.value for m in e],
                )
            ),
            nullable=False,
            server_default=text("'{}'"),
        ),
    )

    # Per-stage metadata, keyed by StageName value. See shape above.
    stages: Optional[dict] = Field(
        default_factory=dict,
        sa_column=Column(
            MutableDict.as_mutable(JSONB),
            nullable=True,
            server_default=text("'{}'::jsonb"),
        ),
    )

    # original file
    file_metadata: dict = Field(
        default_factory=dict,
        sa_column=Column(
            MutableDict.as_mutable(JSONB),
            nullable=False,
            server_default=text("'{}'::jsonb"),
        ),
    )

    # Failure and retry
    failed_stage: Optional[StageName] = Field(
        default=None,
        sa_column=Column(
            SaEnum(
                StageName,
                name="failed_stage_enum",
                native_enum=False,
                length=32,
                values_callable=lambda e: [m.value for m in e],
            ),
            nullable=True,
        ),
    )

    # Timeline

    # use header response -> last_modified_at
    uploaded_at: Optional[datetime] = Field(
        default=None, sa_column=Column(DateTime(timezone=True))
    )

    completed_at: Optional[datetime] = Field(
        default=None, sa_column=Column(DateTime(timezone=True))
    )

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )

    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(
            DateTime(timezone=True),
            nullable=False,
            onupdate=lambda: datetime.now(timezone.utc),
        ),
    )

    deleted_at: Optional[datetime] = Field(
        default=None, sa_column=Column(DateTime(timezone=True))
    )

    # NOTE :- add indexes later, once design is solid and confirmed
