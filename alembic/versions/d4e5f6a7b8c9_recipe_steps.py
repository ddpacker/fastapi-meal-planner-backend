"""recipe_steps table; migrate recipes.instructions into ordered steps

Revision ID: d4e5f6a7b8c9
Revises: c8d9e0f1a2b3
Create Date: 2026-07-17

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "d4e5f6a7b8c9"
down_revision: Union[str, Sequence[str], None] = "c8d9e0f1a2b3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "recipe_steps",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("recipe_id", sa.Integer(), nullable=False),
        sa.Column("step_number", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
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
        sa.ForeignKeyConstraint(["recipe_id"], ["recipes.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_recipe_steps_id"), "recipe_steps", ["id"], unique=False)
    op.create_index(
        op.f("ix_recipe_steps_recipe_id"), "recipe_steps", ["recipe_id"], unique=False
    )

    connection = op.get_bind()
    recipes = connection.execute(sa.text("SELECT id, instructions FROM recipes")).fetchall()
    for recipe_id, instructions in recipes:
        parts = [p.strip() for p in (instructions or "").split("\n") if p.strip()]
        if not parts:
            parts = [instructions or ""]
        for step_number, text in enumerate(parts, start=1):
            connection.execute(
                sa.text(
                    "INSERT INTO recipe_steps "
                    "(recipe_id, step_number, text, created_at, updated_at) "
                    "VALUES (:recipe_id, :step_number, :text, now(), now())"
                ),
                {"recipe_id": recipe_id, "step_number": step_number, "text": text},
            )

    op.drop_column("recipes", "instructions")


def downgrade() -> None:
    op.add_column(
        "recipes",
        sa.Column("instructions", sa.Text(), nullable=True),
    )

    connection = op.get_bind()
    recipe_ids = connection.execute(sa.text("SELECT id FROM recipes")).fetchall()
    for (recipe_id,) in recipe_ids:
        steps = connection.execute(
            sa.text(
                "SELECT text FROM recipe_steps "
                "WHERE recipe_id = :recipe_id "
                "ORDER BY step_number ASC"
            ),
            {"recipe_id": recipe_id},
        ).fetchall()
        instructions = "\n".join(text for (text,) in steps) if steps else ""
        connection.execute(
            sa.text(
                "UPDATE recipes SET instructions = :instructions WHERE id = :recipe_id"
            ),
            {"instructions": instructions, "recipe_id": recipe_id},
        )

    op.alter_column("recipes", "instructions", nullable=False)
    op.drop_index(op.f("ix_recipe_steps_recipe_id"), table_name="recipe_steps")
    op.drop_index(op.f("ix_recipe_steps_id"), table_name="recipe_steps")
    op.drop_table("recipe_steps")
