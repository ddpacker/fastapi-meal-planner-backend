from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import create_access_token
from app.core.deps import get_current_token_payload, get_current_user
from app.db.session import get_db
from app.main import app
from app.models.user import User
from app.schemas.auth import TokenPayload


def test_logout_rejects_further_requests_with_same_token(
    db: Session, user: User
) -> None:
    def override_db():
        yield db

    app.dependency_overrides[get_db] = override_db
    with TestClient(app) as client:
        token = create_access_token(subject=str(user.id))
        headers = {"Authorization": f"Bearer {token}"}
        assert client.get("/meal-plans", headers=headers).status_code == 200
        assert client.post("/auth/logout", headers=headers).status_code == 204
        assert client.get("/meal-plans", headers=headers).status_code == 401
    app.dependency_overrides.clear()


def test_logout_returns_400_when_token_missing_jti(db: Session, user: User) -> None:
    def override_db():
        yield db

    def override_payload() -> TokenPayload:
        return TokenPayload(sub=str(user.id), exp=2_500_000_000, jti=None)

    def override_user() -> User:
        return user

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_token_payload] = override_payload
    app.dependency_overrides[get_current_user] = override_user
    with TestClient(app) as client:
        token = create_access_token(subject=str(user.id))
        headers = {"Authorization": f"Bearer {token}"}
        response = client.post("/auth/logout", headers=headers)
    app.dependency_overrides.clear()

    assert response.status_code == 400
    assert response.json()["detail"] == "Token cannot be revoked"
