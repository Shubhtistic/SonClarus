from typing import Optional
from sqlmodel import SQLModel, Field, DateTime, Relationship, Column, String
from sqlalchemy.dialects.postgresql import JSONB
from datetime import datetime, timezone
from uuid import UUID
from uuid_utils import uuid7
from pydantic import EmailStr

from enum import Enum


class JobStatus(str, Enum):
    QUEUED = "queued"
    DENOISING = "denoising"
    SEPARATING = "separating"
    TRANSCRIBING = "transcribing"
    SUMMARIZING = "summarizing"
    DONE = "done"
    FAILED = "failed"


class User(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid7, primary_key=True)
    email: EmailStr = Field(unique=True, index=True)
    hashed_password: str
    full_name: Optional[str] = Field(default=None)

    is_active: bool = Field(default=True)

    storage_limit: int = Field(default=104857600)  # 100 MB = 104,857,600 bytes
    storage_used: int = Field(default=0)

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_type=DateTime(timezone=True),
    )
    # Relationship: A User has a list of Jobs
    jobs: list["Job"] = Relationship(back_populates="user")

    refresh_tokens: list["RefreshToken"] = Relationship(back_populates="user")


class Job(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid7, primary_key=True)

    filename: str
    object_key: str

    status: JobStatus = Field(default=JobStatus.QUEUED)

    # The Foreign Key (Link to the Parent)
    user_id: UUID = Field(foreign_key="user.id")

    # Relationship: A Job belongs to one User
    user: Optional[User] = Relationship(back_populates="jobs")

    transcript: list[dict] | None = Field(default=None, sa_column=Column(JSONB))
    summary: str | None = Field(default=None, sa_column=Column(String))
    action_items: list[str] | None = Field(default=None, sa_column=Column(JSONB))
    error_message: str | None = Field(default=None, sa_column=Column(String))

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_type=DateTime(timezone=True),
    )


class RefreshToken(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid7, primary_key=True)

    user_id: UUID = Field(foreign_key="user.id", index=True)
    hashed_token: str

    expires_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False)
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )

    user: Optional[User] = Relationship(back_populates="refresh_tokens")
    revoked: bool = Field(default=False)
