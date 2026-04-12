import datetime

import pytest
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.meal_plan import MealPlanWeek, PlannedMeal, PlannedMealRecipe
from app.models.recipe import Recipe, RecipeIngredient
from app.models.user import User
from app.services.grocery_service import generate_grocery_list


@pytest.fixture()
def plan_with_recipes(db: Session, user: User) -> MealPlanWeek:
    plan = MealPlanWeek(
        user_id=user.id,
        start_date=datetime.date(2026, 4, 14),
        end_date=datetime.date(2026, 4, 20),
        title="Test Week",
    )
    db.add(plan)
    db.flush()

    m1 = PlannedMeal(meal_plan_week_id=plan.id, day_index=0, meal_name="Dinner A")
    m2 = PlannedMeal(meal_plan_week_id=plan.id, day_index=1, meal_name="Dinner B")
    db.add_all([m1, m2])
    db.flush()

    r1 = Recipe(
        user_id=user.id,
        title="R1",
        instructions="i",
        servings=2,
        source_model="test",
    )
    r2 = Recipe(
        user_id=user.id,
        title="R2",
        instructions="i",
        servings=2,
        source_model="test",
    )
    db.add_all([r1, r2])
    db.flush()

    db.add_all(
        [
            RecipeIngredient(
                recipe_id=r1.id,
                name="Garlic",
                quantity=2,
                unit="cloves",
                category="produce",
            ),
            RecipeIngredient(
                recipe_id=r2.id,
                name="garlic",
                quantity=3,
                unit="cloves",
                category="produce",
            ),
            RecipeIngredient(
                recipe_id=r2.id,
                name="Soy Sauce",
                quantity=1,
                unit="tbsp",
                category="condiments",
            ),
        ]
    )
    db.add_all(
        [
            PlannedMealRecipe(planned_meal_id=m1.id, recipe_id=r1.id, role="entree"),
            PlannedMealRecipe(planned_meal_id=m2.id, recipe_id=r2.id, role="entree"),
        ]
    )
    db.commit()
    db.refresh(plan)
    return plan


class TestGenerateGroceryList:
    def test_aggregates_same_ingredient_across_recipes(
        self, db: Session, user: User, plan_with_recipes: MealPlanWeek
    ):
        result = generate_grocery_list(plan_with_recipes.id, db, user)

        assert result.meal_plan_week_id == plan_with_recipes.id
        assert "Grocery List for Test Week" == result.title
        items = sorted(result.items, key=lambda i: i.name)
        assert len(items) == 2
        garlic = next(i for i in items if i.name.lower().startswith("garlic"))
        assert garlic.total_quantity == 5
        assert garlic.unit == "cloves"
        soy = next(i for i in items if "Soy" in i.name)
        assert soy.total_quantity == 1
        assert soy.unit == "tbsp"

    def test_unknown_plan_raises_404(self, db: Session, user: User):
        with pytest.raises(HTTPException) as exc:
            generate_grocery_list(99999, db, user)
        assert exc.value.status_code == 404

    def test_no_recipe_links_raises_400(self, db: Session, user: User):
        plan = MealPlanWeek(
            user_id=user.id,
            start_date=datetime.date(2026, 4, 14),
            end_date=datetime.date(2026, 4, 20),
        )
        db.add(plan)
        db.flush()
        db.add(PlannedMeal(meal_plan_week_id=plan.id, day_index=0, meal_name="Lonely"))
        db.commit()

        with pytest.raises(HTTPException) as exc:
            generate_grocery_list(plan.id, db, user)
        assert exc.value.status_code == 400
        assert "recipes" in exc.value.detail.lower()

    def test_no_ingredients_raises_400(self, db: Session, user: User):
        plan = MealPlanWeek(
            user_id=user.id,
            start_date=datetime.date(2026, 4, 14),
            end_date=datetime.date(2026, 4, 20),
        )
        db.add(plan)
        db.flush()
        meal = PlannedMeal(meal_plan_week_id=plan.id, day_index=0, meal_name="M")
        db.add(meal)
        db.flush()
        recipe = Recipe(
            user_id=user.id,
            title="Empty",
            instructions="x",
            servings=1,
            source_model="test",
        )
        db.add(recipe)
        db.flush()
        db.add(PlannedMealRecipe(planned_meal_id=meal.id, recipe_id=recipe.id, role="entree"))
        db.commit()

        with pytest.raises(HTTPException) as exc:
            generate_grocery_list(plan.id, db, user)
        assert exc.value.status_code == 400
        assert "ingredients" in exc.value.detail.lower()
