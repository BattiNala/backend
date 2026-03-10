"""use numeric for lat long

Revision ID: 1074cda7b0d5
Revises: 31eb9c854ad9
Create Date: 2026-03-09 19:49:05.148828

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "1074cda7b0d5"
down_revision: Union[str, Sequence[str], None] = "31eb9c854ad9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute(
        "ALTER TABLE teams ALTER COLUMN base_latitude TYPE NUMERIC(8,4) USING base_latitude::numeric(8,4);"
    )
    op.execute(
        "ALTER TABLE teams ALTER COLUMN base_longitude TYPE NUMERIC(8,4) USING base_longitude::numeric(8,4);"
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.execute(
        "ALTER TABLE teams ALTER COLUMN base_latitude TYPE varchar(50) USING base_latitude::varchar;"
    )
    op.execute(
        "ALTER TABLE teams ALTER COLUMN base_longitude TYPE varchar(50) USING base_longitude::varchar;"
    )
