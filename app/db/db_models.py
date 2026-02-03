from sqlmodel import SQLModel, Field, DateTime
from datetime import datetime, timezone
import uuid
from pydantic import EmailStr


class ProcessJob(SQLModel, table=True):
    id: int = Field(default=None, primary_key=True)
    job_id: str = Field(unique=True, index=True)
    filename: str
    status: str = Field(default="Pending")
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_type=DateTime(timezone=True),
    )
    # we use sa_type to tell postgres that we need an timezone aware column


class User(SQLModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    email: EmailStr = Field(unique=True, index=True)
    hashed_password: str

    storage_limit: int = Field(default=104_857_600)  # 100 MB = 104,857,600 bytes
    storage_used: int = Field(default=0)

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_type=DateTime(timezone=True),
    )
