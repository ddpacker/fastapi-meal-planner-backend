from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base

JsonType = JSON().with_variant(JSONB(), "postgresql")


class RecipeNutrition(Base):
    __tablename__ = "recipe_nutrition"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    recipe_id: Mapped[int] = mapped_column(
        ForeignKey("recipes.id"), unique=True, index=True, nullable=False
    )

    calories: Mapped[float | None] = mapped_column(Numeric(12, 4), nullable=True)
    protein_g: Mapped[float | None] = mapped_column(Numeric(12, 4), nullable=True)
    carbs_g: Mapped[float | None] = mapped_column(Numeric(12, 4), nullable=True)
    fat_g: Mapped[float | None] = mapped_column(Numeric(12, 4), nullable=True)
    fiber_g: Mapped[float | None] = mapped_column(Numeric(12, 4), nullable=True)
    sugar_g: Mapped[float | None] = mapped_column(Numeric(12, 4), nullable=True)
    sodium_mg: Mapped[float | None] = mapped_column(Numeric(12, 4), nullable=True)

    micro_nutrients_json: Mapped[list | dict | None] = mapped_column(JsonType, nullable=True)
    per_serving: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    source: Mapped[str | None] = mapped_column(String(100), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    recipe = relationship("Recipe", back_populates="recipe_nutrition")


class IngredientNutrition(Base):
    __tablename__ = "ingredient_nutrition"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    fdc_id: Mapped[int] = mapped_column(Integer, index=True, nullable=False)
    ingredient_id: Mapped[int] = mapped_column(
        ForeignKey("ingredients.id"), unique=True, index=True, nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    nutrient_data_json: Mapped[list] = mapped_column(JsonType, nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_checked: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    source_version: Mapped[str | None] = mapped_column(String(100), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    ingredient = relationship("Ingredient", back_populates="nutrition")
