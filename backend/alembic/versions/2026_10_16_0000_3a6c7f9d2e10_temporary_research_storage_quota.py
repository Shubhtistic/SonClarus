"""temporarily raise user storage quota to 10 GiB for research tests

Revision ID: 3a6c7f9d2e10
Revises: b384d2a71c40
Create Date: 2026-10-16 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "3a6c7f9d2e10"
down_revision: str | Sequence[str] | None = "b384d2a71c40"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PREVIOUS_LIMIT_BYTES = 524_288_000  # 500 MiB
TEMPORARY_LIMIT_BYTES = 10_737_418_240  # 10 GiB


def upgrade() -> None:
    """Raise standard account quotas and the database default to 10 GiB."""
    op.execute(
        sa.text(
            "UPDATE users SET storage_limit = :new_limit "
            "WHERE storage_limit = :old_limit"
        ).bindparams(
            new_limit=TEMPORARY_LIMIT_BYTES,
            old_limit=PREVIOUS_LIMIT_BYTES,
        )
    )
    op.alter_column(
        "users",
        "storage_limit",
        existing_type=sa.BigInteger(),
        existing_nullable=False,
        server_default=str(TEMPORARY_LIMIT_BYTES),
    )


def downgrade() -> None:
    """Restore standard quotas for accounts still on the temporary quota."""
    op.execute(
        sa.text(
            "UPDATE users SET storage_limit = :old_limit "
            "WHERE storage_limit = :temporary_limit"
        ).bindparams(
            old_limit=PREVIOUS_LIMIT_BYTES,
            temporary_limit=TEMPORARY_LIMIT_BYTES,
        )
    )
    op.alter_column(
        "users",
        "storage_limit",
        existing_type=sa.BigInteger(),
        existing_nullable=False,
        server_default=str(PREVIOUS_LIMIT_BYTES),
    )
