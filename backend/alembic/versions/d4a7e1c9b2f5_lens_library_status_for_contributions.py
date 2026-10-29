"""the shared library: opt in, get reviewed, become visible

Revision ID: d4a7e1c9b2f5
Revises: b1f0a2c4d7e3
Create Date: 2026-10-20 18:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "d4a7e1c9b2f5"
down_revision: Union[str, Sequence[str], None] = "b1f0a2c4d7e3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """contribution state on lenses: none, submitted, approved, rejected."""
    op.add_column("lenses", sa.Column("library_status", sa.Text(), nullable=True))
    op.add_column("lenses", sa.Column("contributed_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("lenses", "contributed_at")
    op.drop_column("lenses", "library_status")
