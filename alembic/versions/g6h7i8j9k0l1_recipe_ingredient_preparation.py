"""add nullable preparation to recipe_ingredients

Revision ID: g6h7i8j9k0l1
Revises: e5f6a7b8c9d0
Create Date: 2026-08-13

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "g6h7i8j9k0l1"
down_revision: Union[str, Sequence[str], None] = "e5f6a7b8c9d0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "recipe_ingredients",
        sa.Column("preparation", sa.String(length=255), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("recipe_ingredients", "preparation")
