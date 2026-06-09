import datetime

from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.security import create_access_token, get_password_hash, verify_password
from app.db.session import get_db
from app.main import app
from app.models.chat import ChatMessage, ChatSession
from app.models.grocery import GroceryItem, GroceryList
from app.models.meal_plan import (
    MealCourseRole,
    MealPlanWeek,
    PlannedMeal,
    PlannedMealCourse,
    PlannedMealRecipe,
)
from app.models.nutrition import NutritionInfo
from app.models.recipe import Recipe, RecipeIngredient
from app.models.user import User
from app.models.user_preferences import UserPreferences


def _make_client(db: Session) -> TestClient:
    def override_db():
        yield db

    app.dependency_overrides[get_db] = override_db
    return TestClient(app)


def _auth_headers(user: User) -> dict[str, str]:
    token = create_access_token(subject=str(user.id))
    return {"Authorization": f"Bearer {token}"}


def test_get_me_returns_user_read(db: Session) -> None:
    user = User(
        email="profile@example.com",
        password_hash=get_password_hash("securepass123"),
    )
    db.add(user)
    db.commit()

    with _make_client(db) as client:
        response = client.get("/users/me", headers=_auth_headers(user))

    app.dependency_overrides.clear()

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == user.id
    assert data["email"] == "profile@example.com"
    assert "created_at" in data
    assert "password_hash" not in data


def test_get_me_without_token_returns_401(db: Session) -> None:
    with _make_client(db) as client:
        response = client.get("/users/me")

    app.dependency_overrides.clear()

    assert response.status_code == 401


def test_patch_me_email_success(db: Session) -> None:
    user = User(
        email="old@example.com",
        password_hash=get_password_hash("securepass123"),
    )
    db.add(user)
    db.commit()

    with _make_client(db) as client:
        response = client.patch(
            "/users/me",
            headers=_auth_headers(user),
            json={"email": "new@example.com", "current_password": "securepass123"},
        )

    app.dependency_overrides.clear()

    assert response.status_code == 200
    data = response.json()
    assert data["email"] == "new@example.com"
    db.refresh(user)
    assert user.email == "new@example.com"


def test_patch_me_email_without_current_password_returns_422(db: Session) -> None:
    user = User(
        email="no-pass@example.com",
        password_hash=get_password_hash("securepass123"),
    )
    db.add(user)
    db.commit()

    with _make_client(db) as client:
        response = client.patch(
            "/users/me",
            headers=_auth_headers(user),
            json={"email": "new@example.com"},
        )

    app.dependency_overrides.clear()

    assert response.status_code == 422
    db.refresh(user)
    assert user.email == "no-pass@example.com"


def test_patch_me_email_wrong_current_password_returns_400(db: Session) -> None:
    user = User(
        email="email-pass@example.com",
        password_hash=get_password_hash("correct-password"),
    )
    db.add(user)
    db.commit()

    with _make_client(db) as client:
        response = client.patch(
            "/users/me",
            headers=_auth_headers(user),
            json={"email": "new@example.com", "current_password": "wrong-password"},
        )

    app.dependency_overrides.clear()

    assert response.status_code == 400
    assert response.json()["detail"] == "Incorrect current password"
    db.refresh(user)
    assert user.email == "email-pass@example.com"


def test_patch_me_duplicate_email_returns_400(db: Session) -> None:
    existing = User(
        email="taken@example.com",
        password_hash=get_password_hash("otherpass123"),
    )
    user = User(
        email="mine@example.com",
        password_hash=get_password_hash("securepass123"),
    )
    db.add_all([existing, user])
    db.commit()

    with _make_client(db) as client:
        response = client.patch(
            "/users/me",
            headers=_auth_headers(user),
            json={"email": "taken@example.com", "current_password": "securepass123"},
        )

    app.dependency_overrides.clear()

    assert response.status_code == 400
    assert response.json()["detail"] == "Email already registered"


def test_patch_me_wrong_current_password_returns_400(db: Session) -> None:
    user = User(
        email="pass@example.com",
        password_hash=get_password_hash("correct-password"),
    )
    db.add(user)
    db.commit()

    with _make_client(db) as client:
        response = client.patch(
            "/users/me",
            headers=_auth_headers(user),
            json={
                "password": "newpassword123",
                "current_password": "wrong-password",
            },
        )

    app.dependency_overrides.clear()

    assert response.status_code == 400
    assert response.json()["detail"] == "Incorrect current password"


def test_patch_me_password_success(db: Session) -> None:
    user = User(
        email="changepass@example.com",
        password_hash=get_password_hash("old-password"),
    )
    db.add(user)
    db.commit()

    with _make_client(db) as client:
        response = client.patch(
            "/users/me",
            headers=_auth_headers(user),
            json={
                "password": "newpassword123",
                "current_password": "old-password",
            },
        )

    app.dependency_overrides.clear()

    assert response.status_code == 200
    db.refresh(user)
    assert verify_password("newpassword123", user.password_hash)


def test_patch_me_without_token_returns_401(db: Session) -> None:
    with _make_client(db) as client:
        response = client.patch("/users/me", json={"email": "new@example.com"})

    app.dependency_overrides.clear()

    assert response.status_code == 401


def test_get_me_includes_default_preferences(db: Session) -> None:
    user = User(
        email="prefs@example.com",
        password_hash=get_password_hash("securepass123"),
    )
    db.add(user)
    db.commit()

    with _make_client(db) as client:
        response = client.get("/users/me", headers=_auth_headers(user))

    app.dependency_overrides.clear()

    assert response.status_code == 200
    data = response.json()
    assert data["preferences"]["unit_system"] == "metric"


def test_get_preferences_returns_default_metric(db: Session) -> None:
    user = User(
        email="getprefs@example.com",
        password_hash=get_password_hash("securepass123"),
    )
    db.add(user)
    db.commit()

    with _make_client(db) as client:
        response = client.get("/users/me/preferences", headers=_auth_headers(user))

    app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {"unit_system": "metric"}


def test_patch_preferences_persists_unit_system(db: Session) -> None:
    user = User(
        email="patchprefs@example.com",
        password_hash=get_password_hash("securepass123"),
    )
    db.add(user)
    db.commit()

    with _make_client(db) as client:
        patch_response = client.patch(
            "/users/me/preferences",
            headers=_auth_headers(user),
            json={"unit_system": "imperial"},
        )
        get_response = client.get("/users/me/preferences", headers=_auth_headers(user))

    app.dependency_overrides.clear()

    assert patch_response.status_code == 200
    assert patch_response.json() == {"unit_system": "imperial"}
    assert get_response.status_code == 200
    assert get_response.json() == {"unit_system": "imperial"}


def test_preferences_without_token_returns_401(db: Session) -> None:
    with _make_client(db) as client:
        get_response = client.get("/users/me/preferences")
        patch_response = client.patch(
            "/users/me/preferences",
            json={"unit_system": "imperial"},
        )

    app.dependency_overrides.clear()

    assert get_response.status_code == 401
    assert patch_response.status_code == 401


def test_delete_me_wrong_password_returns_400(db: Session) -> None:
    user = User(
        email="delete@example.com",
        password_hash=get_password_hash("correct-password"),
    )
    db.add(user)
    db.commit()

    with _make_client(db) as client:
        response = client.request(
            "DELETE",
            "/users/me",
            headers=_auth_headers(user),
            json={"password": "wrong-password"},
        )

    app.dependency_overrides.clear()

    assert response.status_code == 400
    assert response.json()["detail"] == "Incorrect password"
    assert db.get(User, user.id) is not None


def test_delete_me_without_token_returns_401(db: Session) -> None:
    with _make_client(db) as client:
        response = client.request(
            "DELETE",
            "/users/me",
            json={"password": "any-password"},
        )

    app.dependency_overrides.clear()

    assert response.status_code == 401


def test_delete_me_cascades_all_related_rows(db: Session) -> None:
    user = User(
        email="cascade@example.com",
        password_hash=get_password_hash("delete-me-password"),
    )
    db.add(user)
    db.flush()

    prefs = UserPreferences(user_id=user.id)
    plan = MealPlanWeek(
        user_id=user.id,
        start_date=datetime.date(2026, 6, 1),
        end_date=datetime.date(2026, 6, 7),
        title="Delete Week",
    )
    db.add_all([prefs, plan])
    db.flush()

    meal = PlannedMeal(meal_plan_week_id=plan.id, day_index=0, meal_name="Dinner")
    db.add(meal)
    db.flush()

    course = PlannedMealCourse(
        planned_meal_id=meal.id,
        role=MealCourseRole.entree,
        description=None,
    )
    recipe = Recipe(
        user_id=user.id,
        title="Cascade Recipe",
        instructions="Cook it",
        servings=2,
    )
    db.add_all([course, recipe])
    db.flush()

    grocery_list = GroceryList(meal_plan_week_id=plan.id, title="Shop")
    chat_session = ChatSession(recipe_id=recipe.id, user_id=user.id, title="Chat")
    db.add_all(
        [
            PlannedMealRecipe(
                planned_meal_id=meal.id,
                planned_meal_course_id=course.id,
                recipe_id=recipe.id,
                role=MealCourseRole.entree,
            ),
            RecipeIngredient(
                recipe_id=recipe.id,
                name="carrot",
                quantity=100,
                unit="gram",
                category="produce",
            ),
            NutritionInfo(recipe_id=recipe.id, calories=250),
            grocery_list,
            chat_session,
        ]
    )
    db.flush()

    db.add_all(
        [
            GroceryItem(grocery_list_id=grocery_list.id, name="carrot"),
            ChatMessage(chat_session_id=chat_session.id, role="user", content="hello"),
        ]
    )
    db.commit()

    user_id = user.id
    tables = [
        UserPreferences,
        MealPlanWeek,
        PlannedMeal,
        PlannedMealCourse,
        PlannedMealRecipe,
        GroceryList,
        GroceryItem,
        Recipe,
        RecipeIngredient,
        NutritionInfo,
        ChatSession,
        ChatMessage,
    ]
    for model in tables:
        assert db.execute(select(func.count()).select_from(model)).scalar() > 0

    with _make_client(db) as client:
        response = client.request(
            "DELETE",
            "/users/me",
            headers=_auth_headers(user),
            json={"password": "delete-me-password"},
        )

    app.dependency_overrides.clear()

    assert response.status_code == 204
    assert db.get(User, user_id) is None
    for model in tables:
        assert db.execute(select(func.count()).select_from(model)).scalar() == 0
