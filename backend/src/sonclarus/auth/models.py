from datetime import UTC, datetime
from uuid import UUID, uuid7

from sqlalchemy import Column, DateTime, ForeignKey
from sqlmodel import Field, SQLModel


class RefreshTokens(SQLModel, table=True):
    __tablename__ = "refresh_tokens"

    id: UUID = Field(primary_key=True, default_factory=uuid7)
    user_id: UUID = Field(
        sa_column=Column(ForeignKey("users.id"), index=True, nullable=False)
    )

    is_revoked: bool = Field(default=False)

    hashed_token: str = Field(index=True, unique=True, max_length=64)

    # example -> expires_at + 90 days
    # users should not infinetely slide the window of expiry
    max_window_limit: datetime = Field(sa_column=Column(DateTime(timezone=True)))

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        sa_column=Column(DateTime(timezone=True)),
    )

    expires_at: datetime = Field(sa_column=Column(DateTime(timezone=True)))

    revoked_at: datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=True))
    )
