from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.ingredient import Ingredient
from app.models.nutrition import IngredientNutrition, RecipeNutrition
from app.models.recipe import Recipe, RecipeIngredient
from app.models.user import User
from app.services.ingredient_service import extract_preparation
from app.services.ingredient_service import get_or_create as get_or_create_ingredient
from app.services.nutrition_service import ensure_and_calculate
from app.services.usda_client import FakeUsdaClient, UsdaFoodResult


def _food(name: str, calories: float = 165.0, extras: list[dict] | None = None) -> UsdaFoodResult:
    nutrients = [
        {"nutrient_id": 1008, "name": "Energy", "unit": "KCAL", "amount": calories},
        {"nutrient_id": 1003, "name": "Protein", "unit": "G", "amount": 31.0},
        {"nutrient_id": 1005, "name": "Carbohydrate, by difference", "unit": "G", "amount": 0.0},
        {"nutrient_id": 1004, "name": "Total lipid (fat)", "unit": "G", "amount": 3.6},
        {"nutrient_id": 1079, "name": "Fiber, total dietary", "unit": "G", "amount": 0.0},
        {"nutrient_id": 2000, "name": "Sugars, total including NLEA", "unit": "G", "amount": 0.0},
        {"nutrient_id": 1093, "name": "Sodium, Na", "unit": "MG", "amount": 74.0},
        {"nutrient_id": 1087, "name": "Calcium, Ca", "unit": "MG", "amount": 15.0},
    ]
    if extras:
        nutrients.extend(extras)
    return UsdaFoodResult(
        fdc_id=171077,
        name=name,
        nutrient_data=nutrients,
        source_version="2024-10-31",
    )


def _recipe_with_line(
    db: Session,
    user: User,
    *,
    name: str,
    quantity: float,
    unit: str,
    servings: int = 2,
    preparation: str | None = None,
) -> Recipe:
    recipe = Recipe(user_id=user.id, title="Test", servings=servings)
    db.add(recipe)
    db.flush()
    catalog = get_or_create_ingredient(db, name, "meat")
    db.add(
        RecipeIngredient(
            recipe_id=recipe.id,
            ingredient_id=catalog.id,
            quantity=quantity,
            unit=unit,
            preparation=preparation,
        )
    )
    db.flush()
    return recipe


class TestEnsureAndCalculate:
    def test_calories_match_usda_scaled_per_serving(self, db: Session, user: User):
        recipe = _recipe_with_line(db, user, name="chicken breast", quantity=200, unit="gram")
        client = FakeUsdaClient(foods={"chicken breast": _food("chicken breast")})

        nutrition = ensure_and_calculate(db, recipe, client)
        db.commit()

        assert float(nutrition.calories) == 165.0
        assert float(nutrition.protein_g) == 31.0
        assert nutrition.per_serving is True
        assert nutrition.source == "usda"
        assert any(m["nutrient_id"] == 1087 for m in nutrition.micro_nutrients_json)

    def test_skips_usda_when_ingredient_nutrition_exists(self, db: Session, user: User):
        recipe = _recipe_with_line(db, user, name="chicken breast", quantity=200, unit="gram")
        client = FakeUsdaClient(foods={"chicken breast": _food("chicken breast")})
        ensure_and_calculate(db, recipe, client)
        db.commit()

        recipe2 = Recipe(user_id=user.id, title="Second", servings=2)
        db.add(recipe2)
        db.flush()
        catalog = db.execute(
            select(Ingredient).where(Ingredient.name == "chicken breast")
        ).scalar_one()
        db.add(
            RecipeIngredient(
                recipe_id=recipe2.id,
                ingredient_id=catalog.id,
                quantity=100,
                unit="gram",
            )
        )
        db.flush()

        nutrition = ensure_and_calculate(db, recipe2, client)
        db.commit()

        assert client.recorded_calls == ["chicken breast"]
        assert float(nutrition.calories) == 82.5
        assert db.execute(select(IngredientNutrition)).scalars().all().__len__() == 1

    def test_prepared_variants_share_one_ingredient_nutrition_row(self, db: Session, user: User):
        recipe = Recipe(user_id=user.id, title="Rice", servings=1)
        db.add(recipe)
        db.flush()

        cooked_base, cooked_prep = extract_preparation("cooked jasmine rice")
        plain_base, plain_prep = extract_preparation("jasmine rice")
        cooked = get_or_create_ingredient(db, cooked_base, "pantry")
        plain = get_or_create_ingredient(db, plain_base, "pantry")
        db.add(
            RecipeIngredient(
                recipe_id=recipe.id,
                ingredient_id=cooked.id,
                quantity=100,
                unit="gram",
                preparation=cooked_prep,
            )
        )
        db.add(
            RecipeIngredient(
                recipe_id=recipe.id,
                ingredient_id=plain.id,
                quantity=100,
                unit="gram",
                preparation=plain_prep,
            )
        )
        db.flush()

        rice = _food("jasmine rice", calories=130.0)
        client = FakeUsdaClient(foods={"jasmine rice": rice})
        nutrition = ensure_and_calculate(db, recipe, client)
        db.commit()

        ingredients = db.execute(select(Ingredient)).scalars().all()
        assert len(ingredients) == 1
        rows = db.execute(select(IngredientNutrition)).scalars().all()
        assert len(rows) == 1
        assert rows[0].name == "jasmine rice"
        assert client.recorded_calls == ["jasmine rice"]
        assert float(nutrition.calories) == 260.0

    def test_unmatched_unit_is_skipped_other_lines_still_sum(self, db: Session, user: User):
        recipe = Recipe(user_id=user.id, title="Mixed", servings=1)
        db.add(recipe)
        db.flush()
        chicken = get_or_create_ingredient(db, "chicken breast", "meat")
        yolk = get_or_create_ingredient(db, "egg yolk", "dairy")
        db.add(
            RecipeIngredient(
                recipe_id=recipe.id, ingredient_id=chicken.id, quantity=200, unit="gram"
            )
        )
        db.add(
            RecipeIngredient(
                recipe_id=recipe.id, ingredient_id=yolk.id, quantity=4, unit="each"
            )
        )
        db.flush()
        client = FakeUsdaClient(
            foods={
                "chicken breast": _food("chicken breast"),
                "egg yolk": _food("egg yolk", calories=669.0),
            }
        )

        nutrition = ensure_and_calculate(db, recipe, client)
        db.commit()

        # 200g at 165 kcal/100g; egg yolk skipped (count unit "each")
        assert float(nutrition.calories) == 330.0

    def test_only_unmatched_lines_leaves_macros_null(self, db: Session, user: User):
        recipe = _recipe_with_line(db, user, name="chicken breast", quantity=1, unit="each")
        client = FakeUsdaClient(foods={"chicken breast": _food("chicken breast")})

        nutrition = ensure_and_calculate(db, recipe, client)
        db.commit()

        assert nutrition.calories is None
        assert nutrition.protein_g is None
        assert nutrition.micro_nutrients_json is None

    def test_kilogram_unit_scales(self, db: Session, user: User):
        recipe = _recipe_with_line(
            db, user, name="chicken breast", quantity=0.2, unit="kilogram", servings=1
        )
        client = FakeUsdaClient(foods={"chicken breast": _food("chicken breast")})

        nutrition = ensure_and_calculate(db, recipe, client)
        db.commit()

        assert float(nutrition.calories) == 330.0

    def test_missing_usda_hit_leaves_macros_null(self, db: Session, user: User):
        recipe = _recipe_with_line(db, user, name="mystery spice", quantity=10, unit="gram")
        client = FakeUsdaClient()

        nutrition = ensure_and_calculate(db, recipe, client)
        db.commit()

        assert nutrition.calories is None
        assert db.execute(select(IngredientNutrition)).scalars().all() == []

    def test_missing_servings_stores_recipe_totals(self, db: Session, user: User):
        recipe = _recipe_with_line(
            db, user, name="chicken breast", quantity=200, unit="gram", servings=2
        )
        recipe.servings = None
        client = FakeUsdaClient(foods={"chicken breast": _food("chicken breast")})

        nutrition = ensure_and_calculate(db, recipe, client)
        db.commit()

        assert nutrition.per_serving is False
        assert float(nutrition.calories) == 330.0
