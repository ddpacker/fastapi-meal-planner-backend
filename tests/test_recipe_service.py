import datetime

import pytest
from sqlalchemy.orm import Session

from app.clients.fake import FakeClient
from app.models.meal_plan import MealPlanWeek, PlannedMeal, PlannedMealRecipe
from app.models.nutrition import NutritionInfo
from app.models.recipe import Recipe, RecipeIngredient
from app.models.user import User
from app.services.recipe_service import generate_recipes_for_plan


@pytest.fixture()
def plan_with_meals(db: Session, user: User) -> MealPlanWeek:
    """A MealPlanWeek with two PlannedMeals in 'draft' status."""
    plan = MealPlanWeek(
        user_id=user.id,
        start_date=datetime.date(2026, 4, 14),
        end_date=datetime.date(2026, 4, 20),
        title="Week 1",
    )
    db.add(plan)
    db.flush()

    db.add_all([
        PlannedMeal(meal_plan_week_id=plan.id, day_index=0, meal_name="Chicken Tacos"),
        PlannedMeal(meal_plan_week_id=plan.id, day_index=1, meal_name="Vegetable Stir Fry"),
    ])
    db.flush()
    return plan


class TestGenerateRecipesForPlan:
    def test_fake_client_receives_meal_names(self, db: Session, user: User, plan_with_meals: MealPlanWeek):
        """FakeClient.generate_recipes is called with the meal names from the plan."""
        client = FakeClient()

        generate_recipes_for_plan(plan_with_meals.id, db, client, user)

        assert len(client.recorded_calls) == 1
        call = client.recorded_calls[0]
        assert call.method == "generate_recipes"
        assert call.kwargs["meal_names"] == ["Chicken Tacos", "Vegetable Stir Fry"]

    def test_fake_client_returns_recipes_persisted(self, db: Session, user: User, plan_with_meals: MealPlanWeek):
        """Recipes returned by FakeClient are written to the database."""
        client = FakeClient()

        generate_recipes_for_plan(plan_with_meals.id, db, client, user)

        recipes = db.query(Recipe).filter(Recipe.user_id == user.id).all()
        assert len(recipes) == 2
        titles = {r.title for r in recipes}
        # FakeClient cycles through sample_recipes.json fixtures
        assert "Chicken Tacos" in titles
        assert "Vegetable Stir Fry" in titles

    def test_ingredients_persisted(self, db: Session, user: User, plan_with_meals: MealPlanWeek):
        """Ingredients from the FakeClient fixture are stored for each recipe."""
        client = FakeClient()

        generate_recipes_for_plan(plan_with_meals.id, db, client, user)

        ingredients = db.query(RecipeIngredient).all()
        assert len(ingredients) > 0
        names = {i.name for i in ingredients}
        # Both fixture recipes contain these
        assert "chicken breast" in names
        assert "broccoli florets" in names

    def test_nutrition_info_persisted(self, db: Session, user: User, plan_with_meals: MealPlanWeek):
        """NutritionInfo rows are created for recipes that include nutrition_estimate."""
        client = FakeClient()

        generate_recipes_for_plan(plan_with_meals.id, db, client, user)

        nutrition_rows = db.query(NutritionInfo).all()
        assert len(nutrition_rows) == 2
        calories = {n.calories for n in nutrition_rows}
        assert 450.0 in calories   # Chicken Tacos fixture
        assert 220.0 in calories   # Vegetable Stir Fry fixture

    def test_planned_meal_status_updated(self, db: Session, user: User, plan_with_meals: MealPlanWeek):
        """PlannedMeal.status is set to 'planned' after recipe generation."""
        client = FakeClient()

        generate_recipes_for_plan(plan_with_meals.id, db, client, user)

        meals = db.query(PlannedMeal).filter(
            PlannedMeal.meal_plan_week_id == plan_with_meals.id
        ).all()
        assert all(m.status == "planned" for m in meals)

    def test_planned_meal_recipe_links_created(self, db: Session, user: User, plan_with_meals: MealPlanWeek):
        """A PlannedMealRecipe link with role='entree' is created for every meal."""
        client = FakeClient()

        generate_recipes_for_plan(plan_with_meals.id, db, client, user)

        links = db.query(PlannedMealRecipe).all()
        assert len(links) == 2
        assert all(link.role == "entree" for link in links)

    def test_regeneration_replaces_old_recipes(self, db: Session, user: User, plan_with_meals: MealPlanWeek):
        """Calling generate twice replaces the old recipes rather than duplicating them."""
        client = FakeClient()

        generate_recipes_for_plan(plan_with_meals.id, db, client, user)
        generate_recipes_for_plan(plan_with_meals.id, db, client, user)

        recipes = db.query(Recipe).filter(Recipe.user_id == user.id).all()
        assert len(recipes) == 2  # still two, not four

    def test_empty_plan_returns_early(self, db: Session, user: User):
        """A plan with no meals returns immediately without calling the AI client."""
        plan = MealPlanWeek(
            user_id=user.id,
            start_date=datetime.date(2026, 4, 14),
            end_date=datetime.date(2026, 4, 20),
        )
        db.add(plan)
        db.flush()

        client = FakeClient()
        result = generate_recipes_for_plan(plan.id, db, client, user)

        assert client.recorded_calls == []
        assert result.id == plan.id

    def test_missing_plan_raises_404(self, db: Session, user: User):
        """Requesting a non-existent plan_id raises HTTP 404."""
        from fastapi import HTTPException

        client = FakeClient()
        with pytest.raises(HTTPException) as exc_info:
            generate_recipes_for_plan(9999, db, client, user)

        assert exc_info.value.status_code == 404
