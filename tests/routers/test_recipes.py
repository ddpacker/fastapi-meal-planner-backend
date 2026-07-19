from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

import datetime

from app.core.security import create_access_token, get_password_hash
from app.db.session import get_db
from app.main import app
from app.models.meal_plan import (
    MealCourseRole,
    MealPlanWeek,
    PlannedMeal,
    PlannedMealCourse,
    PlannedMealRecipe,
)
from app.models.nutrition import NutritionInfo
from app.models.recipe import Recipe, RecipeIngredient, RecipeStep
from app.models.user import User
from app.services.ingredient_service import get_or_create as get_or_create_ingredient


def _make_client(db: Session) -> TestClient:
    def override_db():
        yield db

    app.dependency_overrides[get_db] = override_db
    return TestClient(app)


def _auth_headers(user: User) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(subject=str(user.id))}"}


def _add_recipe(
    db: Session,
    user: User,
    *,
    title: str,
    source_model: str | None = None,
    servings: int = 2,
) -> Recipe:
    recipe = Recipe(
        user_id=user.id,
        title=title,
        servings=servings,
        source_model=source_model,
    )
    db.add(recipe)
    db.flush()
    return recipe


def test_list_recipes_returns_summaries_for_current_user(db: Session, user: User) -> None:
    other = User(email="other@example.com", password_hash=get_password_hash("x"))
    db.add(other)
    db.flush()

    mine = _add_recipe(db, user, title="Chicken Tacos", source_model="anthropic")
    _add_recipe(db, user, title="Green Salad", source_model=None)
    _add_recipe(db, other, title="Other User Recipe", source_model="anthropic")
    db.commit()

    client = _make_client(db)
    response = client.get("/recipes", headers=_auth_headers(user))
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    assert {row["title"] for row in data} == {"Chicken Tacos", "Green Salad"}
    assert all("steps" not in row and "ingredients" not in row for row in data)
    assert data[0]["id"] >= data[1]["id"]
    assert any(row["id"] == mine.id and row["source_model"] == "anthropic" for row in data)


def test_list_recipes_filters_by_search_and_source_model(db: Session, user: User) -> None:
    _add_recipe(db, user, title="Chicken Tacos", source_model="anthropic")
    _add_recipe(db, user, title="Chicken Soup", source_model="test")
    _add_recipe(db, user, title="Beef Stew", source_model="anthropic")
    db.commit()

    client = _make_client(db)
    response = client.get(
        "/recipes",
        params={"search": "chicken", "source_model": "anthropic"},
        headers=_auth_headers(user),
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["title"] == "Chicken Tacos"


def test_list_recipes_paginates(db: Session, user: User) -> None:
    for i in range(5):
        _add_recipe(db, user, title=f"Recipe {i}")
    db.commit()

    client = _make_client(db)
    page1 = client.get(
        "/recipes",
        params={"page": 1, "page_size": 2},
        headers=_auth_headers(user),
    )
    page2 = client.get(
        "/recipes",
        params={"page": 2, "page_size": 2},
        headers=_auth_headers(user),
    )
    assert page1.status_code == 200
    assert page2.status_code == 200
    assert len(page1.json()) == 2
    assert len(page2.json()) == 2
    assert {row["id"] for row in page1.json()}.isdisjoint({row["id"] for row in page2.json()})


def test_list_recipes_requires_auth(db: Session) -> None:
    client = _make_client(db)
    assert client.get("/recipes").status_code == 401


def test_create_recipe_persists_steps_and_catalog_ingredients(db: Session, user: User) -> None:
    payload = {
        "title": "Manual Soup",
        "servings": 3,
        "steps": [
            {"step_number": 1, "text": "Simmer broth"},
            {"step_number": 2, "text": "Add vegetables"},
        ],
        "ingredients": [
            {"name": "Carrot", "quantity": 100, "unit": "gram", "category": "produce"},
            {"name": "Salt", "quantity": 2, "unit": "gram", "category": "spices"},
        ],
    }
    client = _make_client(db)
    response = client.post("/recipes", json=payload, headers=_auth_headers(user))
    assert response.status_code == 201
    data = response.json()
    assert data["title"] == "Manual Soup"
    assert data["servings"] == 3
    assert len(data["steps"]) == 2
    assert {i["ingredient"]["name"] for i in data["ingredients"]} == {"carrot", "salt"}

    recipe_id = data["id"]
    db.expire_all()
    recipe = db.execute(select(Recipe).where(Recipe.id == recipe_id)).scalar_one()
    assert recipe.user_id == user.id
    assert recipe.source_model is None
    steps = db.execute(
        select(RecipeStep).where(RecipeStep.recipe_id == recipe_id).order_by(RecipeStep.step_number)
    ).scalars().all()
    assert [s.text for s in steps] == ["Simmer broth", "Add vegetables"]
    ings = db.execute(
        select(RecipeIngredient).where(RecipeIngredient.recipe_id == recipe_id)
    ).scalars().all()
    assert {i.ingredient.name for i in ings} == {"carrot", "salt"}


def test_get_recipe_returns_nested_details(db: Session, user: User) -> None:
    recipe = _add_recipe(db, user, title="Detail Recipe", source_model="test")
    catalog = get_or_create_ingredient(db, "lime", "produce")
    db.add(RecipeStep(recipe_id=recipe.id, step_number=1, text="Squeeze lime"))
    db.add(
        RecipeIngredient(
            recipe_id=recipe.id, ingredient_id=catalog.id, quantity=1, unit="piece"
        )
    )
    db.commit()

    client = _make_client(db)
    response = client.get(f"/recipes/{recipe.id}", headers=_auth_headers(user))
    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "Detail Recipe"
    assert data["steps"][0]["text"] == "Squeeze lime"
    assert data["ingredients"][0]["ingredient"]["name"] == "lime"
    assert data["ingredients"][0]["quantity"] == 1.0


def test_get_recipe_other_user_returns_404(db: Session, user: User) -> None:
    other = User(email="other@example.com", password_hash=get_password_hash("x"))
    db.add(other)
    db.flush()
    foreign = _add_recipe(db, other, title="Secret")
    db.commit()

    client = _make_client(db)
    assert (
        client.get(f"/recipes/{foreign.id}", headers=_auth_headers(user)).status_code == 404
    )


def test_get_recipes_for_meal_returns_linked_recipes(db: Session, user: User) -> None:
    plan = MealPlanWeek(
        user_id=user.id,
        start_date=datetime.date(2026, 4, 14),
        end_date=datetime.date(2026, 4, 20),
    )
    db.add(plan)
    db.flush()
    meal = PlannedMeal(meal_plan_week_id=plan.id, day_index=0, meal_name="Dinner")
    db.add(meal)
    db.flush()
    course = PlannedMealCourse(
        planned_meal_id=meal.id, role=MealCourseRole.entree, description=None
    )
    recipe = _add_recipe(db, user, title="Linked Entree")
    db.add(course)
    db.flush()
    db.add(
        PlannedMealRecipe(
            planned_meal_id=meal.id,
            planned_meal_course_id=course.id,
            recipe_id=recipe.id,
            role=MealCourseRole.entree,
        )
    )
    db.commit()

    client = _make_client(db)
    response = client.get(f"/recipes/meals/{meal.id}", headers=_auth_headers(user))
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["title"] == "Linked Entree"
    assert data[0]["id"] == recipe.id


def test_put_recipe_replaces_steps_and_ingredients(db: Session, user: User) -> None:
    recipe = _add_recipe(db, user, title="Old Title", servings=2)
    old_ing = get_or_create_ingredient(db, "chicken breast", "meat")
    db.add(
        RecipeStep(recipe_id=recipe.id, step_number=1, text="Old step")
    )
    db.add(
        RecipeIngredient(
            recipe_id=recipe.id,
            ingredient_id=old_ing.id,
            quantity=500,
            unit="gram",
        )
    )
    db.commit()

    payload = {
        "title": "New Title",
        "servings": 4,
        "steps": [
            {"step_number": 1, "text": "Prep tofu"},
            {"step_number": 2, "text": "Cook and serve"},
        ],
        "ingredients": [
            {"name": "tofu", "quantity": 200, "unit": "gram", "category": "protein"},
        ],
    }
    client = _make_client(db)
    response = client.put(
        f"/recipes/{recipe.id}",
        json=payload,
        headers=_auth_headers(user),
    )
    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "New Title"
    assert data["servings"] == 4
    assert [s["text"] for s in data["steps"]] == ["Prep tofu", "Cook and serve"]
    assert len(data["ingredients"]) == 1
    assert data["ingredients"][0]["ingredient"]["name"] == "tofu"

    db.expire_all()
    steps = db.execute(
        select(RecipeStep).where(RecipeStep.recipe_id == recipe.id).order_by(RecipeStep.step_number)
    ).scalars().all()
    ings = db.execute(
        select(RecipeIngredient).where(RecipeIngredient.recipe_id == recipe.id)
    ).scalars().all()
    assert [s.text for s in steps] == ["Prep tofu", "Cook and serve"]
    assert len(ings) == 1
    assert ings[0].ingredient.name == "tofu"
    assert (
        db.execute(select(func.count()).select_from(RecipeIngredient)).scalar_one() == 1
    )


def test_put_recipe_unknown_or_other_user_returns_404(db: Session, user: User) -> None:
    other = User(email="other@example.com", password_hash=get_password_hash("x"))
    db.add(other)
    db.flush()
    foreign = _add_recipe(db, other, title="Foreign")
    db.commit()

    payload = {
        "title": "Hijack",
        "servings": 1,
        "steps": [{"step_number": 1, "text": "x"}],
        "ingredients": [],
    }
    client = _make_client(db)
    assert (
        client.put(
            f"/recipes/{foreign.id}",
            json=payload,
            headers=_auth_headers(user),
        ).status_code
        == 404
    )
    assert (
        client.put(
            "/recipes/99999",
            json=payload,
            headers=_auth_headers(user),
        ).status_code
        == 404
    )


def test_delete_recipe_cascades_and_returns_204(db: Session, user: User) -> None:
    plan = MealPlanWeek(
        user_id=user.id,
        start_date=datetime.date(2026, 4, 14),
        end_date=datetime.date(2026, 4, 20),
    )
    db.add(plan)
    db.flush()
    meal = PlannedMeal(meal_plan_week_id=plan.id, day_index=0, meal_name="Dinner")
    db.add(meal)
    db.flush()
    course = PlannedMealCourse(
        planned_meal_id=meal.id, role=MealCourseRole.entree, description=None
    )
    recipe = _add_recipe(db, user, title="To Delete")
    db.add(course)
    db.flush()

    catalog = get_or_create_ingredient(db, "onion", "produce")
    db.add(RecipeStep(recipe_id=recipe.id, step_number=1, text="Chop"))
    db.add(
        RecipeIngredient(
            recipe_id=recipe.id, ingredient_id=catalog.id, quantity=1, unit="piece"
        )
    )
    db.add(NutritionInfo(recipe_id=recipe.id, calories=100))
    db.add(
        PlannedMealRecipe(
            planned_meal_id=meal.id,
            planned_meal_course_id=course.id,
            recipe_id=recipe.id,
            role=MealCourseRole.entree,
        )
    )
    db.commit()
    recipe_id = recipe.id

    client = _make_client(db)
    response = client.delete(f"/recipes/{recipe_id}", headers=_auth_headers(user))
    assert response.status_code == 204

    assert (
        db.execute(select(Recipe).where(Recipe.id == recipe_id)).scalar_one_or_none()
        is None
    )
    assert (
        db.execute(
            select(func.count())
            .select_from(RecipeStep)
            .where(RecipeStep.recipe_id == recipe_id)
        ).scalar_one()
        == 0
    )
    assert (
        db.execute(
            select(func.count())
            .select_from(RecipeIngredient)
            .where(RecipeIngredient.recipe_id == recipe_id)
        ).scalar_one()
        == 0
    )
    assert (
        db.execute(
            select(func.count())
            .select_from(NutritionInfo)
            .where(NutritionInfo.recipe_id == recipe_id)
        ).scalar_one()
        == 0
    )
    assert (
        db.execute(
            select(func.count())
            .select_from(PlannedMealRecipe)
            .where(PlannedMealRecipe.recipe_id == recipe_id)
        ).scalar_one()
        == 0
    )


def test_delete_recipe_unknown_or_other_user_returns_404(db: Session, user: User) -> None:
    other = User(email="other@example.com", password_hash=get_password_hash("x"))
    db.add(other)
    db.flush()
    foreign = _add_recipe(db, other, title="Foreign")
    db.commit()

    client = _make_client(db)
    assert (
        client.delete(f"/recipes/{foreign.id}", headers=_auth_headers(user)).status_code
        == 404
    )
    assert client.delete("/recipes/99999", headers=_auth_headers(user)).status_code == 404
