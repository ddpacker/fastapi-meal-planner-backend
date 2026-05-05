import datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.clients.factory import get_ai_client
from app.clients.fake import FakeClient
from app.core.security import create_access_token
from app.db.session import get_db
from app.main import app
from app.models.meal_plan import (
    MealCourseRole,
    MealPlanWeek,
    PlannedMeal,
    PlannedMealCourse,
)
from app.models.recipe import Recipe
from app.models.user import User


@pytest.fixture()
def fake_ai() -> FakeClient:
    return FakeClient()


@pytest.fixture()
def client(db, user, fake_ai: FakeClient):
    def override_db():
        yield db

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_ai_client] = lambda: fake_ai
    with TestClient(app) as tc:
        yield tc
    app.dependency_overrides.clear()


@pytest.fixture()
def auth_headers(user: User) -> dict[str, str]:
    token = create_access_token(subject=str(user.id))
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def plan_with_meals(db: Session, user: User) -> MealPlanWeek:
    plan = MealPlanWeek(
        user_id=user.id,
        start_date=datetime.date(2026, 4, 14),
        end_date=datetime.date(2026, 4, 20),
        title="HTTP Test Week",
    )
    db.add(plan)
    db.flush()
    m1 = PlannedMeal(meal_plan_week_id=plan.id, day_index=0, meal_name="Tacos")
    m2 = PlannedMeal(meal_plan_week_id=plan.id, day_index=1, meal_name="Stir Fry")
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
    db.commit()
    db.refresh(plan)
    return plan


@pytest.fixture()
def plan_two_courses_one_meal(db: Session, user: User) -> MealPlanWeek:
    plan = MealPlanWeek(
        user_id=user.id,
        start_date=datetime.date(2026, 4, 14),
        end_date=datetime.date(2026, 4, 20),
        title="Two Course Week",
    )
    db.add(plan)
    db.flush()
    m = PlannedMeal(meal_plan_week_id=plan.id, day_index=0, meal_name="Feast")
    db.add(m)
    db.flush()
    db.add_all(
        [
            PlannedMealCourse(planned_meal_id=m.id, role=MealCourseRole.entree, description=None),
            PlannedMealCourse(planned_meal_id=m.id, role=MealCourseRole.side, description=None),
        ]
    )
    db.commit()
    db.refresh(plan)
    return plan


def test_post_generate_recipes_returns_plan_and_invokes_fake_client(
    client: TestClient,
    fake_ai: FakeClient,
    auth_headers: dict[str, str],
    plan_with_meals: MealPlanWeek,
) -> None:
    response = client.post(
        f"/meal-plans/{plan_with_meals.id}/generate-recipes",
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == plan_with_meals.id
    assert data["title"] == "HTTP Test Week"
    assert len(data["planned_meals"]) == 2
    assert {m["meal_name"] for m in data["planned_meals"]} == {"Tacos", "Stir Fry"}
    assert all(m["status"] == "planned" for m in data["planned_meals"])
    for m in data["planned_meals"]:
        assert len(m["courses"]) == 1
        assert m["courses"][0]["role"] == "entree"
        assert m["courses"][0]["description"] is None

    assert len(fake_ai.recorded_calls) == 1
    assert fake_ai.recorded_calls[0].method == "generate_recipes"
    assert fake_ai.recorded_calls[0].kwargs["meals"] == [
        ("Tacos", [(MealCourseRole.entree, None)]),
        ("Stir Fry", [(MealCourseRole.entree, None)]),
    ]


def test_post_meal_plan_creates_default_entree_course(
    client: TestClient,
    auth_headers: dict[str, str],
) -> None:
    response = client.post(
        "/meal-plans",
        headers=auth_headers,
        json={
            "start_date": "2026-04-14",
            "end_date": "2026-04-20",
            "title": "New Week",
            "planned_meals": [
                {"day_index": 0, "meal_name": "Pasta Night", "status": "draft"},
            ],
        },
    )
    assert response.status_code == 201
    meals = response.json()["planned_meals"]
    assert len(meals) == 1
    assert len(meals[0]["courses"]) == 1
    assert meals[0]["courses"][0]["role"] == "entree"
    assert meals[0]["courses"][0]["description"] is None


def test_post_meal_plan_accepts_explicit_courses(
    client: TestClient,
    auth_headers: dict[str, str],
) -> None:
    response = client.post(
        "/meal-plans",
        headers=auth_headers,
        json={
            "start_date": "2026-04-14",
            "end_date": "2026-04-20",
            "title": "Multi",
            "planned_meals": [
                {
                    "day_index": 0,
                    "meal_name": "Pork Night",
                    "status": "draft",
                    "courses": [
                        {"role": "entree", "description": "Bourbon Apple Marinaded Pork Chop"},
                        {"role": "side", "description": None},
                    ],
                },
            ],
        },
    )
    assert response.status_code == 201
    courses = response.json()["planned_meals"][0]["courses"]
    assert len(courses) == 2
    roles = {c["role"] for c in courses}
    assert roles == {"entree", "side"}
    entree = next(c for c in courses if c["role"] == "entree")
    assert entree["description"] == "Bourbon Apple Marinaded Pork Chop"


def test_post_generate_recipes_requires_auth(
    client: TestClient,
    plan_with_meals: MealPlanWeek,
) -> None:
    response = client.post(f"/meal-plans/{plan_with_meals.id}/generate-recipes")
    assert response.status_code == 401


def test_post_generate_recipes_unknown_plan_returns_404(
    client: TestClient,
    auth_headers: dict[str, str],
) -> None:
    response = client.post("/meal-plans/99999/generate-recipes", headers=auth_headers)
    assert response.status_code == 404


def test_patch_planned_meal_name_and_status_without_ai(
    client: TestClient,
    fake_ai: FakeClient,
    auth_headers: dict[str, str],
    plan_with_meals: MealPlanWeek,
    db: Session,
) -> None:
    meal = db.execute(
        select(PlannedMeal).where(
            PlannedMeal.meal_plan_week_id == plan_with_meals.id,
            PlannedMeal.day_index == 0,
        )
    ).scalar_one()
    response = client.patch(
        f"/meal-plans/{plan_with_meals.id}/meals/{meal.id}",
        headers=auth_headers,
        json={"meal_name": "Taco Tuesday", "status": "planned"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["meal_name"] == "Taco Tuesday"
    assert data["status"] == "planned"
    assert fake_ai.recorded_calls == []


def test_patch_planned_meal_not_found_wrong_plan(
    client: TestClient,
    auth_headers: dict[str, str],
    plan_with_meals: MealPlanWeek,
    db: Session,
) -> None:
    meal = db.execute(
        select(PlannedMeal).where(
            PlannedMeal.meal_plan_week_id == plan_with_meals.id,
            PlannedMeal.day_index == 0,
        )
    ).scalar_one()
    response = client.patch(
        f"/meal-plans/99999/meals/{meal.id}",
        headers=auth_headers,
        json={"meal_name": "Nope"},
    )
    assert response.status_code == 404


def test_patch_add_course_generates_only_new_slot(
    client: TestClient,
    fake_ai: FakeClient,
    auth_headers: dict[str, str],
    plan_with_meals: MealPlanWeek,
    db: Session,
) -> None:
    client.post(
        f"/meal-plans/{plan_with_meals.id}/generate-recipes",
        headers=auth_headers,
    )
    fake_ai.recorded_calls.clear()

    meal = db.execute(
        select(PlannedMeal).where(
            PlannedMeal.meal_plan_week_id == plan_with_meals.id,
            PlannedMeal.day_index == 0,
        )
    ).scalar_one()
    entree = db.execute(
        select(PlannedMealCourse).where(
            PlannedMealCourse.planned_meal_id == meal.id,
            PlannedMealCourse.role == MealCourseRole.entree,
        )
    ).scalar_one()

    response = client.patch(
        f"/meal-plans/{plan_with_meals.id}/meals/{meal.id}",
        headers=auth_headers,
        json={
            "courses": [
                {"id": entree.id, "role": "entree", "description": None},
                {"role": "side", "description": "Green salad"},
            ],
        },
    )
    assert response.status_code == 200
    assert len(response.json()["courses"]) == 2

    gen_calls = [c for c in fake_ai.recorded_calls if c.method == "generate_recipes"]
    assert len(gen_calls) == 1
    assert gen_calls[0].kwargs["meals"] == [
        ("Tacos", [(MealCourseRole.side, "Green salad")]),
    ]


def test_patch_remove_course_deletes_orphan_recipe(
    client: TestClient,
    auth_headers: dict[str, str],
    plan_two_courses_one_meal: MealPlanWeek,
    db: Session,
) -> None:
    plan = plan_two_courses_one_meal
    client.post(f"/meal-plans/{plan.id}/generate-recipes", headers=auth_headers)
    assert db.execute(select(func.count()).select_from(Recipe)).scalar_one() == 2

    meal = db.execute(
        select(PlannedMeal).where(PlannedMeal.meal_plan_week_id == plan.id)
    ).scalar_one()
    courses = (
        db.execute(
            select(PlannedMealCourse)
            .where(PlannedMealCourse.planned_meal_id == meal.id)
            .order_by(PlannedMealCourse.id)
        )
        .scalars()
        .all()
    )
    entree, side = courses[0], courses[1]
    removed_course_id = side.id

    response = client.patch(
        f"/meal-plans/{plan.id}/meals/{meal.id}",
        headers=auth_headers,
        json={
            "courses": [{"id": entree.id, "role": "entree", "description": None}],
        },
    )
    assert response.status_code == 200
    assert len(response.json()["courses"]) == 1
    assert db.execute(select(func.count()).select_from(Recipe)).scalar_one() == 1
    assert db.get(PlannedMealCourse, removed_course_id) is None


def test_patch_course_description_regenerates_single_slot(
    client: TestClient,
    fake_ai: FakeClient,
    auth_headers: dict[str, str],
    plan_with_meals: MealPlanWeek,
    db: Session,
) -> None:
    client.post(
        f"/meal-plans/{plan_with_meals.id}/generate-recipes",
        headers=auth_headers,
    )
    fake_ai.recorded_calls.clear()

    meal = db.execute(
        select(PlannedMeal).where(
            PlannedMeal.meal_plan_week_id == plan_with_meals.id,
            PlannedMeal.day_index == 0,
        )
    ).scalar_one()
    course = db.execute(
        select(PlannedMealCourse).where(PlannedMealCourse.planned_meal_id == meal.id)
    ).scalar_one()

    response = client.patch(
        f"/meal-plans/{plan_with_meals.id}/meals/{meal.id}",
        headers=auth_headers,
        json={
            "courses": [
                {"id": course.id, "role": "entree", "description": "Chili lime marinade"},
            ],
        },
    )
    assert response.status_code == 200
    assert response.json()["courses"][0]["description"] == "Chili lime marinade"

    gen_calls = [c for c in fake_ai.recorded_calls if c.method == "generate_recipes"]
    assert len(gen_calls) == 1
    assert gen_calls[0].kwargs["meals"] == [
        ("Tacos", [(MealCourseRole.entree, "Chili lime marinade")]),
    ]


def test_patch_course_role_change_replaces_course_row(
    client: TestClient,
    fake_ai: FakeClient,
    auth_headers: dict[str, str],
    plan_with_meals: MealPlanWeek,
    db: Session,
) -> None:
    client.post(
        f"/meal-plans/{plan_with_meals.id}/generate-recipes",
        headers=auth_headers,
    )
    fake_ai.recorded_calls.clear()

    meal = db.execute(
        select(PlannedMeal).where(
            PlannedMeal.meal_plan_week_id == plan_with_meals.id,
            PlannedMeal.day_index == 0,
        )
    ).scalar_one()
    old_course = db.execute(
        select(PlannedMealCourse).where(PlannedMealCourse.planned_meal_id == meal.id)
    ).scalar_one()
    old_id = old_course.id

    response = client.patch(
        f"/meal-plans/{plan_with_meals.id}/meals/{meal.id}",
        headers=auth_headers,
        json={
            "courses": [{"id": old_course.id, "role": "side", "description": None}],
        },
    )
    assert response.status_code == 200
    new_id = response.json()["courses"][0]["id"]
    assert new_id != old_id
    assert response.json()["courses"][0]["role"] == "side"
    assert db.get(PlannedMealCourse, old_id) is None

    gen_calls = [c for c in fake_ai.recorded_calls if c.method == "generate_recipes"]
    assert len(gen_calls) == 1
    assert gen_calls[0].kwargs["meals"] == [("Tacos", [(MealCourseRole.side, None)])]
