"""rename nutrition_info to recipe_nutrition; add ingredient_nutrition

Revision ID: h7i8j9k0l1m2
Revises: g6h7i8j9k0l1
Create Date: 2026-08-16

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "h7i8j9k0l1m2"
down_revision: Union[str, Sequence[str], None] = "g6h7i8j9k0l1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_MACRO_COLS = (
    "calories",
    "protein_g",
    "carbs_g",
    "fat_g",
    "fiber_g",
    "sugar_g",
    "sodium_mg",
)


def upgrade() -> None:
    op.rename_table("nutrition_info", "recipe_nutrition")
    op.drop_index("ix_nutrition_info_id", table_name="recipe_nutrition")
    op.drop_index("ix_nutrition_info_recipe_id", table_name="recipe_nutrition")
    op.create_index("ix_recipe_nutrition_id", "recipe_nutrition", ["id"], unique=False)
    op.create_index(
        "ix_recipe_nutrition_recipe_id",
        "recipe_nutrition",
        ["recipe_id"],
        unique=True,
    )
    for col in _MACRO_COLS:
        op.alter_column(
            "recipe_nutrition",
            col,
            existing_type=sa.Float(),
            type_=sa.Numeric(12, 4),
            existing_nullable=True,
        )
    op.add_column(
        "recipe_nutrition",
        sa.Column("micro_nutrients_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )

    op.create_table(
        "ingredient_nutrition",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("fdc_id", sa.Integer(), nullable=False),
        sa.Column("ingredient_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("nutrient_data_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_checked", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source_version", sa.String(length=100), nullable=True),
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
        sa.ForeignKeyConstraint(["ingredient_id"], ["ingredients.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ingredient_nutrition_id", "ingredient_nutrition", ["id"], unique=False)
    op.create_index("ix_ingredient_nutrition_fdc_id", "ingredient_nutrition", ["fdc_id"], unique=False)
    op.create_index(
        "ix_ingredient_nutrition_ingredient_id",
        "ingredient_nutrition",
        ["ingredient_id"],
        unique=True,
    )
    op.create_index(
        "ix_ingredient_nutrition_name",
        "ingredient_nutrition",
        ["name"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_ingredient_nutrition_name", table_name="ingredient_nutrition")
    op.drop_index("ix_ingredient_nutrition_ingredient_id", table_name="ingredient_nutrition")
    op.drop_index("ix_ingredient_nutrition_fdc_id", table_name="ingredient_nutrition")
    op.drop_index("ix_ingredient_nutrition_id", table_name="ingredient_nutrition")
    op.drop_table("ingredient_nutrition")

    op.drop_column("recipe_nutrition", "micro_nutrients_json")
    for col in _MACRO_COLS:
        op.alter_column(
            "recipe_nutrition",
            col,
            existing_type=sa.Numeric(12, 4),
            type_=sa.Float(),
            existing_nullable=True,
        )
    op.drop_index("ix_recipe_nutrition_recipe_id", table_name="recipe_nutrition")
    op.drop_index("ix_recipe_nutrition_id", table_name="recipe_nutrition")
    op.rename_table("recipe_nutrition", "nutrition_info")
    op.create_index("ix_nutrition_info_id", "nutrition_info", ["id"], unique=False)
    op.create_index("ix_nutrition_info_recipe_id", "nutrition_info", ["recipe_id"], unique=False)
