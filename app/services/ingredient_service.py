from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.ingredient import Ingredient


def normalize_ingredient_name(name: str) -> str:
    return name.lower().strip()


def get_or_create(db: Session, name: str, category: str | None = None) -> Ingredient:
    normalized = normalize_ingredient_name(name)
    existing = db.execute(
        select(Ingredient).where(Ingredient.name == normalized)
    ).scalar_one_or_none()
    if existing is not None:
        return existing

    ingredient = Ingredient(name=normalized, category=category)
    db.add(ingredient)
    db.flush()
    return ingredient
