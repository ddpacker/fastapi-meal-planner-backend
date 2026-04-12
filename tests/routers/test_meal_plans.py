import datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.clients.factory import get_ai_client
from app.clients.fake import FakeClient
from app.core.security import create_access_token
from app.db.session import get_db
from app.main import app
from app.models.meal_plan import MealPlanWeek, PlannedMeal
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
    db.add_all(
        [
            PlannedMeal(meal_plan_week_id=plan.id, day_index=0, meal_name="Tacos"),
            PlannedMeal(meal_plan_week_id=plan.id, day_index=1, meal_name="Stir Fry"),
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

    assert len(fake_ai.recorded_calls) == 1
    assert fake_ai.recorded_calls[0].method == "generate_recipes"
    assert fake_ai.recorded_calls[0].kwargs["meal_names"] == ["Tacos", "Stir Fry"]


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
