from typing import Optional
from sqlmodel import SQLModel, Field, DateTime, Relationship
from datetime import datetime, timezone
import uuid
from pydantic import EmailStr

from enum import Enum


class JobStatus(str, Enum):
    PENDING = "Pending"
    PROCESSING = "Processing"
    COMPLETED = "Completed"
    FAILED = "Failed"


class User(SQLModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    email: EmailStr = Field(unique=True, index=True)
    hashed_password: str
    full_name: str = Field(default=None)

    is_active: bool = Field(default=True)

    storage_limit: int = Field(default=104857600)  # 100 MB = 104,857,600 bytes
    storage_used: int = Field(default=0)

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_type=DateTime(timezone=True),
    )
    # Relationship: A User has a list of Jobs
    jobs: list["Job"] = Relationship(back_populates="user")


class Job(SQLModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)

    filename: str
    filepath: str

    status: JobStatus = Field(default=JobStatus.PENDING)

    # The Foreign Key (Link to the Parent)
    user_id: uuid.UUID = Field(foreign_key="user.id")

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_type=DateTime(timezone=True),
    )
    # Relationship: A Job belongs to one User
    user: Optional[User] = Relationship(back_populates="jobs")
