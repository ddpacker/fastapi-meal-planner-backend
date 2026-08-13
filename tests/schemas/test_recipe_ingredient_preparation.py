from app.models.ingredient import Ingredient
from app.models.recipe import RecipeIngredient
from app.schemas.recipes import RecipeIngredientRead


def test_recipe_ingredient_read_serializes_null_preparation() -> None:
    ingredient = Ingredient(id=1, name="jasmine rice", category="pantry")
    row = RecipeIngredient(
        id=1,
        recipe_id=1,
        ingredient_id=1,
        quantity=200,
        unit="gram",
        preparation=None,
        ingredient=ingredient,
    )

    data = RecipeIngredientRead.model_validate(row).model_dump()

    assert data["preparation"] is None
    assert data["ingredient"]["name"] == "jasmine rice"


def test_recipe_ingredient_read_serializes_explicit_preparation() -> None:
    ingredient = Ingredient(id=1, name="jasmine rice", category="pantry")
    row = RecipeIngredient(
        id=2,
        recipe_id=1,
        ingredient_id=1,
        quantity=200,
        unit="gram",
        preparation="cooked",
        ingredient=ingredient,
    )

    data = RecipeIngredientRead.model_validate(row).model_dump()

    assert data["preparation"] == "cooked"
