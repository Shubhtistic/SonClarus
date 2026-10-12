from datetime import datetime, timezone
from typing import Optional
from uuid import UUID, uuid7
from sqlmodel import SQLModel, Field
from sqlalchemy import CheckConstraint, Column, DateTime, BigInteger


class User(SQLModel, table=True):
    __tablename__ = "users"

    id: UUID = Field(default_factory=uuid7, primary_key=True)

    email: str = Field(unique=True, index=True, max_length=100)
    hashed_password: str = Field(max_length=60)

    first_name: str = Field(max_length=50)
    last_name: str = Field(max_length=50)

    is_active: bool = Field(default=True)

    # for now we will keep as true, in future when email verification is added it will be false
    is_verified: bool = Field(default=True)

    storage_limit: int = Field(
        default=524288000,
        sa_column=Column(BigInteger, nullable=False, server_default="524288000"),
    )  # 500 MiB

    storage_used: int = Field(
        default=0,
        sa_column=Column(BigInteger, nullable=False, server_default="0"),
    )

    last_login_at: Optional[datetime] = Field(
        default=None, sa_column=Column(DateTime(timezone=True))
    )

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True)),
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(
            DateTime(timezone=True), onupdate=lambda: datetime.now(timezone.utc)
        ),
    )

    deleted_at: Optional[datetime] = Field(
        default=None, sa_column=Column(DateTime(timezone=True))
    )

    __table_args__ = (
        CheckConstraint("storage_used >= 0", name="ck_users_storage_used_non_negative"),
    )
