from sqlmodel import SQLModel, Field, DateTime
from datetime import datetime, timezone


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
