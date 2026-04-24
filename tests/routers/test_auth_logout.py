from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import create_access_token
from app.db.session import get_db
from app.main import app
from app.models.user import User


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
