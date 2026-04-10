"""add embedding for similarity search

Revision ID: 60b54533c0f7
Revises: bb4d23f8222a
Create Date: 2026-04-10 13:26:10.273123
"""

from typing import Sequence, Union

import sqlalchemy as sa
from pgvector.sqlalchemy import Vector

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "60b54533c0f7"
down_revision: Union[str, Sequence[str], None] = "bb4d23f8222a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.add_column(
        "attachments",
        sa.Column("embedding", Vector(1536), nullable=True),
    )
    op.add_column(
        "attachments",
        sa.Column("embedding_model", sa.String(length=100), nullable=True),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("attachments", "embedding_model")
    op.drop_column("attachments", "embedding")
