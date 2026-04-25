from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import create_access_token, get_password_hash
from app.db.session import get_db
from app.main import app
from app.models.user import User


def _make_client(db: Session) -> TestClient:
    def override_db():
        yield db

    app.dependency_overrides[get_db] = override_db
    return TestClient(app)


def test_register_user_success(db: Session) -> None:
    with _make_client(db) as client:
        response = client.post(
            "/auth/register",
            json={"email": "new-user@example.com", "password": "securepass123"},
        )

    app.dependency_overrides.clear()

    assert response.status_code == 201
    data = response.json()
    assert data["email"] == "new-user@example.com"
    assert isinstance(data["id"], int)
    assert "created_at" in data


def test_register_duplicate_email_returns_400(db: Session) -> None:
    existing = User(
        email="dupe@example.com",
        password_hash=get_password_hash("already-used-password"),
    )
    db.add(existing)
    db.commit()

    with _make_client(db) as client:
        response = client.post(
            "/auth/register",
            json={"email": "dupe@example.com", "password": "anotherpass123"},
        )

    app.dependency_overrides.clear()

    assert response.status_code == 400
    assert response.json()["detail"] == "Email already registered"


def test_login_returns_access_token(db: Session) -> None:
    user = User(
        email="login@example.com",
        password_hash=get_password_hash("valid-password"),
    )
    db.add(user)
    db.commit()

    with _make_client(db) as client:
        response = client.post(
            "/auth/login",
            data={"username": "login@example.com", "password": "valid-password"},
        )

    app.dependency_overrides.clear()

    assert response.status_code == 200
    data = response.json()
    assert data["token_type"] == "bearer"
    assert isinstance(data["access_token"], str)
    assert data["access_token"]


def test_login_bad_password_returns_401(db: Session) -> None:
    user = User(
        email="wrong-pass@example.com",
        password_hash=get_password_hash("real-password"),
    )
    db.add(user)
    db.commit()

    with _make_client(db) as client:
        response = client.post(
            "/auth/login",
            data={"username": "wrong-pass@example.com", "password": "not-it"},
        )

    app.dependency_overrides.clear()

    assert response.status_code == 401
    assert response.json()["detail"] == "Incorrect email or password"


def test_protected_endpoint_rejects_missing_token(db: Session, user: User) -> None:
    with _make_client(db) as client:
        response = client.get("/meal-plans")

    app.dependency_overrides.clear()

    assert response.status_code == 401


def test_protected_endpoint_accepts_valid_token(db: Session, user: User) -> None:
    token = create_access_token(subject=str(user.id))

    with _make_client(db) as client:
        response = client.get("/meal-plans", headers={"Authorization": f"Bearer {token}"})

    app.dependency_overrides.clear()

    assert response.status_code == 200
