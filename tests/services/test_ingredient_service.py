from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.ingredient import Ingredient
from app.models.recipe import Recipe, RecipeIngredient
from app.models.user import User
from app.services.ingredient_service import (
    extract_preparation,
    get_or_create,
    normalize_ingredient_name,
    normalize_unit,
)


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


class TestNormalizeUnit:
    def test_defaults_missing_to_each(self):
        assert normalize_unit(None) == "each"
        assert normalize_unit("") == "each"
        assert normalize_unit("  ") == "each"
        assert normalize_unit("none") == "each"
        assert normalize_unit("NULL") == "each"
        assert normalize_unit("n/a") == "each"

    def test_normalizes_real_units(self):
        assert normalize_unit(" Gram ") == "gram"
        assert normalize_unit("EACH") == "each"
        assert normalize_unit("piece") == "piece"


class TestExtractPreparation:
    def test_strips_leading_preparation_word(self):
        assert extract_preparation("cooked jasmine rice") == ("jasmine rice", "cooked")

    def test_strips_day_old(self):
        assert extract_preparation("day-old jasmine rice") == ("jasmine rice", "day-old")

    def test_plain_name_leaves_preparation_none(self):
        assert extract_preparation("jasmine rice") == ("jasmine rice", None)

    def test_normalizes_base_name_after_strip(self):
        assert extract_preparation("  Cooked Jasmine Rice  ") == ("jasmine rice", "cooked")


class TestPreparationCollapse:
    def test_prepared_variants_share_one_ingredient_row(self, db: Session, user: User):
        recipe = Recipe(user_id=user.id, title="Rice Bowl", servings=2)
        db.add(recipe)
        db.flush()

        cooked_base, cooked_prep = extract_preparation("cooked jasmine rice")
        day_old_base, day_old_prep = extract_preparation("day-old jasmine rice")
        plain_base, plain_prep = extract_preparation("jasmine rice")

        cooked_ing = get_or_create(db, cooked_base, "pantry")
        day_old_ing = get_or_create(db, day_old_base, "pantry")
        plain_ing = get_or_create(db, plain_base, "pantry")

        db.add(
            RecipeIngredient(
                recipe_id=recipe.id,
                ingredient_id=cooked_ing.id,
                quantity=200,
                unit="gram",
                preparation=cooked_prep,
            )
        )
        db.add(
            RecipeIngredient(
                recipe_id=recipe.id,
                ingredient_id=day_old_ing.id,
                quantity=150,
                unit="gram",
                preparation=day_old_prep,
            )
        )
        db.add(
            RecipeIngredient(
                recipe_id=recipe.id,
                ingredient_id=plain_ing.id,
                quantity=100,
                unit="gram",
                preparation=plain_prep,
            )
        )
        db.commit()

        ingredients = db.execute(select(Ingredient)).scalars().all()
        assert len(ingredients) == 1
        assert ingredients[0].name == "jasmine rice"

        rows = db.execute(
            select(RecipeIngredient).where(RecipeIngredient.recipe_id == recipe.id)
        ).scalars().all()
        by_prep = {row.preparation: row for row in rows}
        assert set(by_prep) == {"cooked", "day-old", None}
        assert by_prep["cooked"].ingredient_id == ingredients[0].id
        assert by_prep["day-old"].ingredient_id == ingredients[0].id
        assert by_prep[None].ingredient_id == ingredients[0].id
