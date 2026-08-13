from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.ingredient import Ingredient

_PREPARATION_WORDS = frozenset(
    {
        "cooked",
        "day-old",
        "fresh",
        "frozen",
        "dried",
        "raw",
        "diced",
        "minced",
        "chopped",
        "sliced",
        "roasted",
        "toasted",
        "ground",
        "whole",
    }
)


def normalize_ingredient_name(name: str) -> str:
    return name.lower().strip()


def extract_preparation(name: str) -> tuple[str, str | None]:
    tokens = name.strip().split()
    if not tokens:
        return normalize_ingredient_name(name), None

    stripped: list[str] = []
    while tokens and tokens[0].lower() in _PREPARATION_WORDS:
        stripped.append(tokens.pop(0).lower())
    while tokens and tokens[-1].lower() in _PREPARATION_WORDS:
        stripped.append(tokens.pop().lower())

    if not tokens:
        return normalize_ingredient_name(name), None

    base_name = normalize_ingredient_name(" ".join(tokens))
    preparation = " ".join(stripped) if stripped else None
    return base_name, preparation


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
