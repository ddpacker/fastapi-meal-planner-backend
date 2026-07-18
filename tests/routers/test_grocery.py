import datetime

import pytest
from fastapi.testclient import TestClient

from app.core.security import create_access_token
from app.db.session import get_db
from app.main import app
from app.models.meal_plan import (
    MealCourseRole,
    MealPlanWeek,
    PlannedMeal,
    PlannedMealCourse,
    PlannedMealRecipe,
)
from app.models.recipe import Recipe, RecipeIngredient
from app.models.user import User
from app.services.ingredient_service import get_or_create as get_or_create_ingredient


@pytest.fixture()
def client(db, user):
    def override_db():
        yield db

    app.dependency_overrides[get_db] = override_db
    with TestClient(app) as tc:
        yield tc
    app.dependency_overrides.clear()


@pytest.fixture()
def auth_headers(user: User) -> dict[str, str]:
    token = create_access_token(subject=str(user.id))
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def plan_with_linked_recipes(db, user: User) -> MealPlanWeek:
    plan = MealPlanWeek(
        user_id=user.id,
        start_date=datetime.date(2026, 4, 14),
        end_date=datetime.date(2026, 4, 20),
        title="Grocery HTTP Week",
    )
    db.add(plan)
    db.flush()

    meal = PlannedMeal(meal_plan_week_id=plan.id, day_index=0, meal_name="Dinner")
    db.add(meal)
    db.flush()
    course = PlannedMealCourse(
        planned_meal_id=meal.id, role=MealCourseRole.entree, description=None
    )
    db.add(course)
    db.flush()

    recipe = Recipe(
        user_id=user.id,
        title="R1",
        servings=2,
        source_model="test",
    )
    db.add(recipe)
    db.flush()
    onion = get_or_create_ingredient(db, "Onion", "produce")
    db.add(
        RecipeIngredient(
            recipe_id=recipe.id,
            ingredient_id=onion.id,
            quantity=1,
            unit="piece",
        )
    )
    db.add(
        PlannedMealRecipe(
            planned_meal_id=meal.id,
            planned_meal_course_id=course.id,
            recipe_id=recipe.id,
            role=MealCourseRole.entree,
        )
    )
    db.commit()
    db.refresh(plan)
    return plan


def test_post_grocery_list_returns_201_with_items(
    client: TestClient,
    auth_headers: dict[str, str],
    plan_with_linked_recipes: MealPlanWeek,
) -> None:
    response = client.post(
        f"/grocery/meal-plans/{plan_with_linked_recipes.id}/grocery-list",
        headers=auth_headers,
    )
    assert response.status_code == 201
    data = response.json()
    assert data["meal_plan_week_id"] == plan_with_linked_recipes.id
    assert "Grocery List for Grocery HTTP Week" in (data["title"] or "")
    assert len(data["items"]) == 1
    assert data["items"][0]["name"] == "onion"
    assert data["items"][0]["total_quantity"] == 1.0
    assert data["items"][0]["unit"] == "piece"


def test_post_grocery_list_requires_auth(
    client: TestClient,
    plan_with_linked_recipes: MealPlanWeek,
) -> None:
    response = client.post(
        f"/grocery/meal-plans/{plan_with_linked_recipes.id}/grocery-list",
    )
    assert response.status_code == 401


def test_post_grocery_list_unknown_plan_returns_404(
    client: TestClient,
    auth_headers: dict[str, str],
) -> None:
    response = client.post(
        "/grocery/meal-plans/99999/grocery-list",
        headers=auth_headers,
    )
    assert response.status_code == 404
