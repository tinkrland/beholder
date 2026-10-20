"""source chunk page for pdf and docx provenance

Revision ID: b1f0a2c4d7e3
Revises: 98c91ece89eb
Create Date: 2026-10-20 12:59:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "b1f0a2c4d7e3"
down_revision: Union[str, Sequence[str], None] = "98c91ece89eb"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """pdf and docx chunks cite their page: provenance is doc and page."""
    op.add_column("source_chunks", sa.Column("page", sa.Integer(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("source_chunks", "page")
