"""unique meal plan week per user start_date

Revision ID: j9k0l1m2n3o4
Revises: i8j9k0l1m2n3
Create Date: 2026-09-03

"""

from typing import Sequence, Union

from alembic import op

revision: str = "j9k0l1m2n3o4"
down_revision: Union[str, Sequence[str], None] = "i8j9k0l1m2n3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_meal_plan_weeks_user_start",
        "meal_plan_weeks",
        ["user_id", "start_date"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_meal_plan_weeks_user_start",
        "meal_plan_weeks",
        type_="unique",
    )
