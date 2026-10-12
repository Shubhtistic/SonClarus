"""increase default user storage limit to 500 MiB

Revision ID: b384d2a71c40
Revises: 7c1012941b14
Create Date: 2026-10-13 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "b384d2a71c40"
down_revision: Union[str, Sequence[str], None] = "7c1012941b14"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


OLD_LIMIT_BYTES = 104_857_600
NEW_LIMIT_BYTES = 524_288_000


def upgrade() -> None:
    """Raise existing default quotas and the database default to 500 MiB."""
    op.execute(
        sa.text(
            "UPDATE users SET storage_limit = :new_limit "
            "WHERE storage_limit = :old_limit"
        ).bindparams(new_limit=NEW_LIMIT_BYTES, old_limit=OLD_LIMIT_BYTES)
    )
    op.alter_column(
        "users",
        "storage_limit",
        existing_type=sa.BigInteger(),
        existing_nullable=False,
        server_default=str(NEW_LIMIT_BYTES),
    )


def downgrade() -> None:
    """Restore the old database default without reducing existing user quotas."""
    op.alter_column(
        "users",
        "storage_limit",
        existing_type=sa.BigInteger(),
        existing_nullable=False,
        server_default=str(OLD_LIMIT_BYTES),
    )
