import datetime

import pytest
from sqlalchemy.orm import Session

from app.clients.fake import FakeClient
from app.models.meal_plan import (
    MealCourseRole,
    MealPlanWeek,
    PlannedMeal,
    PlannedMealCourse,
    PlannedMealRecipe,
)
from app.models.nutrition import RecipeNutrition
from app.models.recipe import Recipe, RecipeIngredient, RecipeStep
from app.models.user import User
from app.services.recipe_service import generate_recipes_for_plan, list_recipes


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

    m1 = PlannedMeal(meal_plan_week_id=plan.id, day_index=0, meal_name="Chicken Tacos")
    m2 = PlannedMeal(meal_plan_week_id=plan.id, day_index=1, meal_name="Vegetable Stir Fry")
    db.add_all([m1, m2])
    db.flush()
    db.add_all(
        [
            PlannedMealCourse(
                planned_meal_id=m1.id, role=MealCourseRole.entree, description=None
            ),
            PlannedMealCourse(
                planned_meal_id=m2.id, role=MealCourseRole.entree, description=None
            ),
        ]
    )
    db.flush()
    return plan


@pytest.fixture()
def plan_with_multi_course_meal(db: Session, user: User) -> MealPlanWeek:
    plan = MealPlanWeek(
        user_id=user.id,
        start_date=datetime.date(2026, 4, 14),
        end_date=datetime.date(2026, 4, 20),
        title="Pork Week",
    )
    db.add(plan)
    db.flush()
    m = PlannedMeal(meal_plan_week_id=plan.id, day_index=0, meal_name="Pork Night")
    db.add(m)
    db.flush()
    db.add_all(
        [
            PlannedMealCourse(
                planned_meal_id=m.id,
                role=MealCourseRole.entree,
                description="Bourbon Apple Marinaded Pork Chop",
            ),
            PlannedMealCourse(
                planned_meal_id=m.id,
                role=MealCourseRole.side,
                description=None,
            ),
        ]
    )
    db.flush()
    return plan


class TestGenerateRecipesForPlan:
    def test_fake_client_receives_meals_with_course_slots(
        self, db: Session, user: User, plan_with_meals: MealPlanWeek
    ):
        """FakeClient.generate_recipes is called with (meal_name, courses) per planned meal."""
        client = FakeClient()

        generate_recipes_for_plan(plan_with_meals.id, db, client, user)

        assert len(client.recorded_calls) == 1
        call = client.recorded_calls[0]
        assert call.method == "generate_recipes"
        assert call.kwargs["meals"] == [
            ("Chicken Tacos", [(MealCourseRole.entree, None)]),
            ("Vegetable Stir Fry", [(MealCourseRole.entree, None)]),
        ]

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
        names = {i.ingredient.name for i in ingredients}
        # Both fixture recipes contain these
        assert "chicken breast" in names
        assert "broccoli floret" in names

    def test_steps_persisted(self, db: Session, user: User, plan_with_meals: MealPlanWeek):
        client = FakeClient()

        generate_recipes_for_plan(plan_with_meals.id, db, client, user)

        assert client.recorded_calls[0].method == "generate_recipes"
        steps = db.query(RecipeStep).all()
        assert len(steps) > 0
        texts = {s.text for s in steps}
        assert any("Season chicken" in t for t in texts)
        assert any("wok" in t.lower() for t in texts)

    def test_list_recipes_scopes_to_user(self, db: Session, user: User):
        other = User(email="other@example.com", password_hash="x")
        db.add(other)
        db.flush()
        db.add_all(
            [
                Recipe(user_id=user.id, title="Mine", servings=1),
                Recipe(user_id=other.id, title="Theirs", servings=1),
            ]
        )
        db.commit()

        results = list_recipes(db, user, search="Mine")
        assert len(results) == 1
        assert results[0].title == "Mine"

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
        assert all(link.role == MealCourseRole.entree for link in links)
        assert all(link.planned_meal_course_id is not None for link in links)

    def test_multi_course_meal_generates_one_recipe_per_slot(
        self, db: Session, user: User, plan_with_multi_course_meal: MealPlanWeek
    ):
        client = FakeClient()

        generate_recipes_for_plan(plan_with_multi_course_meal.id, db, client, user)

        assert client.recorded_calls[0].kwargs["meals"] == [
            (
                "Pork Night",
                [
                    (MealCourseRole.entree, "Bourbon Apple Marinaded Pork Chop"),
                    (MealCourseRole.side, None),
                ],
            ),
        ]
        recipes = db.query(Recipe).filter(Recipe.user_id == user.id).all()
        assert len(recipes) == 2
        links = db.query(PlannedMealRecipe).all()
        assert len(links) == 2
        assert {link.role for link in links} == {MealCourseRole.entree, MealCourseRole.side}

    def test_regeneration_replaces_old_recipes(self, db: Session, user: User, plan_with_meals: MealPlanWeek):
        """Calling generate twice replaces the old recipes rather than duplicating them."""
        client = FakeClient()

        generate_recipes_for_plan(plan_with_meals.id, db, client, user)
        generate_recipes_for_plan(plan_with_meals.id, db, client, user)

        recipes = db.query(Recipe).filter(Recipe.user_id == user.id).all()
        assert len(recipes) == 2  # still two, not four

    def test_generation_writes_recipe_nutrition(self, db: Session, user: User, plan_with_meals: MealPlanWeek):
        client = FakeClient()
        generate_recipes_for_plan(plan_with_meals.id, db, client, user)

        recipes = db.query(Recipe).filter(Recipe.user_id == user.id).all()
        rows = db.query(RecipeNutrition).all()
        assert len(rows) == len(recipes)
        assert {row.recipe_id for row in rows} == {r.id for r in recipes}
        assert all(row.source == "usda" for row in rows)

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
