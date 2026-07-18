"""global Ingredient catalog; RecipeIngredient becomes association object

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-07-17

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "e5f6a7b8c9d0"
down_revision: Union[str, Sequence[str], None] = "d4e5f6a7b8c9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "ingredients",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("category", sa.String(length=100), nullable=True),
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
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )
    op.create_index(op.f("ix_ingredients_id"), "ingredients", ["id"], unique=False)

    op.execute(
        sa.text(
            "INSERT INTO ingredients (name, category, created_at, updated_at) "
            "SELECT DISTINCT ON (LOWER(TRIM(name))) "
            "LOWER(TRIM(name)), category, now(), now() "
            "FROM recipe_ingredients "
            "ORDER BY LOWER(TRIM(name)), id"
        )
    )

    op.add_column(
        "recipe_ingredients",
        sa.Column("ingredient_id", sa.Integer(), nullable=True),
    )

    op.execute(
        sa.text(
            "UPDATE recipe_ingredients AS ri "
            "SET ingredient_id = i.id "
            "FROM ingredients AS i "
            "WHERE LOWER(TRIM(ri.name)) = i.name"
        )
    )

    op.alter_column("recipe_ingredients", "ingredient_id", nullable=False)
    op.create_index(
        op.f("ix_recipe_ingredients_ingredient_id"),
        "recipe_ingredients",
        ["ingredient_id"],
        unique=False,
    )
    op.create_foreign_key(
        op.f("fk_recipe_ingredients_ingredient_id_ingredients"),
        "recipe_ingredients",
        "ingredients",
        ["ingredient_id"],
        ["id"],
    )

    op.drop_column("recipe_ingredients", "name")
    op.drop_column("recipe_ingredients", "category")


def downgrade() -> None:
    op.add_column(
        "recipe_ingredients",
        sa.Column("category", sa.String(length=100), nullable=True),
    )
    op.add_column(
        "recipe_ingredients",
        sa.Column("name", sa.String(length=255), nullable=True),
    )

    op.execute(
        sa.text(
            "UPDATE recipe_ingredients AS ri "
            "SET name = i.name, category = i.category "
            "FROM ingredients AS i "
            "WHERE ri.ingredient_id = i.id"
        )
    )

    op.alter_column("recipe_ingredients", "name", nullable=False)

    op.drop_constraint(
        op.f("fk_recipe_ingredients_ingredient_id_ingredients"),
        "recipe_ingredients",
        type_="foreignkey",
    )
    op.drop_index(
        op.f("ix_recipe_ingredients_ingredient_id"),
        table_name="recipe_ingredients",
    )
    op.drop_column("recipe_ingredients", "ingredient_id")

    op.drop_index(op.f("ix_ingredients_id"), table_name="ingredients")
    op.drop_table("ingredients")
