import pytest
from fastapi.testclient import TestClient

from app.clients.factory import get_ai_client
from app.clients.fake import FakeClient
from app.core.security import create_access_token
from app.db.session import get_db
from app.main import app
from app.models.chat import ChatSession
from app.models.recipe import Recipe, RecipeIngredient
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
def recipe_and_session(db, user: User) -> tuple[Recipe, ChatSession]:
    recipe = Recipe(
        user_id=user.id,
        title="Test Recipe",
        instructions="Do the thing.",
        servings=2,
        source_model="test",
    )
    db.add(recipe)
    db.flush()
    db.add(
        RecipeIngredient(
            recipe_id=recipe.id,
            name="salt",
            quantity=1,
            unit="tsp",
            category="spices",
        )
    )
    sess = ChatSession(recipe_id=recipe.id, user_id=user.id, title=recipe.title)
    db.add(sess)
    db.commit()
    db.refresh(recipe)
    db.refresh(sess)
    return recipe, sess


def test_post_messages_returns_user_and_assistant_rows(
    client: TestClient,
    fake_ai: FakeClient,
    auth_headers: dict[str, str],
    recipe_and_session: tuple[Recipe, ChatSession],
) -> None:
    _recipe, sess = recipe_and_session
    response = client.post(
        f"/chat/chat-sessions/{sess.id}/messages",
        json={"content": "Please simplify"},
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    assert data[0]["role"] == "user"
    assert data[0]["content"] == "Please simplify"
    assert data[1]["role"] == "assistant"
    assert data[1]["content"] == "Here is your updated recipe."
    assert len(fake_ai.recorded_calls) == 1
    assert fake_ai.recorded_calls[0].method == "chat_modify"


def test_post_messages_requires_auth(
    client: TestClient,
    recipe_and_session: tuple[Recipe, ChatSession],
) -> None:
    _recipe, sess = recipe_and_session
    response = client.post(
        f"/chat/chat-sessions/{sess.id}/messages",
        json={"content": "Hi"},
    )
    assert response.status_code == 401
