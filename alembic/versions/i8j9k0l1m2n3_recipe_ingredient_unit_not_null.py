"""backfill null recipe_ingredient units to each; enforce not null

Revision ID: i8j9k0l1m2n3
Revises: h7i8j9k0l1m2
Create Date: 2026-08-16

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "i8j9k0l1m2n3"
down_revision: Union[str, Sequence[str], None] = "h7i8j9k0l1m2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        sa.text(
            """
            UPDATE recipe_ingredients
            SET unit = 'each'
            WHERE unit IS NULL
               OR btrim(unit) = ''
               OR lower(btrim(unit)) IN ('none', 'null', 'n/a', 'na', '-')
            """
        )
    )
    op.alter_column(
        "recipe_ingredients",
        "unit",
        existing_type=sa.String(length=50),
        nullable=False,
        server_default="each",
    )


def downgrade() -> None:
    op.alter_column(
        "recipe_ingredients",
        "unit",
        existing_type=sa.String(length=50),
        nullable=True,
        server_default=None,
    )
