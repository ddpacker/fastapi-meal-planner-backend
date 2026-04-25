"""planned_meal_courses and planned_meal_recipes.course link

Revision ID: f3a4b5c6d7e8
Revises: a1b2c3d4e5f6
Create Date: 2026-04-25

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "f3a4b5c6d7e8"
down_revision: Union[str, Sequence[str], None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "planned_meal_courses",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("planned_meal_id", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["planned_meal_id"], ["planned_meals.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_planned_meal_courses_id"), "planned_meal_courses", ["id"], unique=False
    )
    op.create_index(
        op.f("ix_planned_meal_courses_planned_meal_id"),
        "planned_meal_courses",
        ["planned_meal_id"],
        unique=False,
    )

    op.execute(
        sa.text(
            "INSERT INTO planned_meal_courses "
            "(planned_meal_id, role, description, created_at, updated_at) "
            "SELECT id, 'entree', NULL, now(), now() FROM planned_meals"
        )
    )

    op.add_column(
        "planned_meal_recipes",
        sa.Column("planned_meal_course_id", sa.Integer(), nullable=True),
    )

    op.execute(
        sa.text(
            "UPDATE planned_meal_recipes AS pmr SET planned_meal_course_id = ("
            "SELECT pmc.id FROM planned_meal_courses AS pmc "
            "WHERE pmc.planned_meal_id = pmr.planned_meal_id "
            "ORDER BY pmc.id ASC LIMIT 1)"
        )
    )

    op.execute(
        sa.text(
            "UPDATE planned_meal_recipes SET role = 'entree' "
            "WHERE role IS NULL OR role NOT IN ('starter', 'entree', 'side', 'dessert')"
        )
    )

    op.alter_column(
        "planned_meal_recipes",
        "planned_meal_course_id",
        existing_type=sa.Integer(),
        nullable=False,
    )
    op.create_foreign_key(
        "fk_planned_meal_recipes_planned_meal_course_id",
        "planned_meal_recipes",
        "planned_meal_courses",
        ["planned_meal_course_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index(
        op.f("ix_planned_meal_recipes_planned_meal_course_id"),
        "planned_meal_recipes",
        ["planned_meal_course_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_planned_meal_recipes_planned_meal_course_id"),
        table_name="planned_meal_recipes",
    )
    op.drop_constraint(
        "fk_planned_meal_recipes_planned_meal_course_id",
        "planned_meal_recipes",
        type_="foreignkey",
    )
    op.drop_column("planned_meal_recipes", "planned_meal_course_id")
    op.drop_index(
        op.f("ix_planned_meal_courses_planned_meal_id"),
        table_name="planned_meal_courses",
    )
    op.drop_index(op.f("ix_planned_meal_courses_id"), table_name="planned_meal_courses")
    op.drop_table("planned_meal_courses")
