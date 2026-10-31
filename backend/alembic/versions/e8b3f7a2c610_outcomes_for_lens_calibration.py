"""outcome reporting to calibrate lens quality

Revision ID: e8b3f7a2c610
Revises: d4a7e1c9b2f5
Create Date: 2026-10-31 16:20:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "e8b3f7a2c610"
down_revision: Union[str, Sequence[str], None] = "d4a7e1c9b2f5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """what actually happened to a target: insert-only history."""
    op.create_table(
        "outcomes",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("target_id", sa.String(length=36), nullable=False),
        sa.Column("outcome", sa.Text(), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("recorded_by", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["target_id"], ["targets.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_outcome_target", "outcomes", ["target_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_outcome_target", table_name="outcomes")
    op.drop_table("outcomes")
