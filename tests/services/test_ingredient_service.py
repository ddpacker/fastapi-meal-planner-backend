from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.ingredient import Ingredient
from app.models.user import User
from app.services.ingredient_service import get_or_create, normalize_ingredient_name


class TestGetOrCreateIngredient:
    def test_creates_normalized_name(self, db: Session, user: User):
        ingredient = get_or_create(db, "  Garlic  ", "produce")
        db.commit()

        assert ingredient.name == "garlic"
        assert ingredient.category == "produce"
        assert (
            db.execute(select(Ingredient).where(Ingredient.name == "garlic")).scalar_one()
            is ingredient
        )

    def test_returns_existing_without_mutating_category(self, db: Session, user: User):
        first = get_or_create(db, "Garlic", "produce")
        db.flush()
        second = get_or_create(db, "GARLIC", "spices")

        assert second.id == first.id
        assert second.category == "produce"
        assert db.execute(select(Ingredient)).scalars().all() == [first]

    def test_normalize_ingredient_name(self):
        assert normalize_ingredient_name("  Carrot ") == "carrot"
