from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import create_access_token, get_password_hash
from app.db.session import get_db
from app.main import app
from app.models.recipe import Recipe
from app.models.user import User


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
