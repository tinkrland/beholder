"""pre-build mode: projects that exist only as specs, where every fact is a
claim. migration adds projects.mode and facts.basis.

Revision ID: f2c9d5b7e804
Revises: e8b3f7a2c610
Create Date: 2026-10-31 17:35:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "f2c9d5b7e804"
down_revision: Union[str, Sequence[str], None] = "e8b3f7a2c610"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """specs-only projects and the claimed/observed distinction on facts."""
    op.add_column("projects", sa.Column("mode", sa.Text(), nullable=False, server_default="build"))
    op.add_column("facts", sa.Column("basis", sa.Text(), nullable=False, server_default="observed"))


def downgrade() -> None:
    op.drop_column("facts", "basis")
    op.drop_column("projects", "mode")
