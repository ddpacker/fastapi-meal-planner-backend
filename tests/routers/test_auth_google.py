import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.db.session import get_db
from app.main import app


@pytest.fixture()
def client_no_google(monkeypatch):
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "")
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "")
    monkeypatch.setenv("GOOGLE_REDIRECT_URI", "")
    get_settings.cache_clear()
    with TestClient(app) as tc:
        yield tc
    get_settings.cache_clear()


@pytest.fixture()
def client_google_configured(monkeypatch):
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "test-client-id")
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "test-secret")
    monkeypatch.setenv("GOOGLE_REDIRECT_URI", "http://localhost:8000/auth/google/callback")
    get_settings.cache_clear()
    with TestClient(app) as tc:
        yield tc
    get_settings.cache_clear()


def test_google_login_returns_503_when_not_configured(client_no_google: TestClient) -> None:
    response = client_no_google.get("/auth/google", follow_redirects=False)
    assert response.status_code == 503


def test_google_login_redirects_when_configured(client_google_configured: TestClient) -> None:
    response = client_google_configured.get("/auth/google", follow_redirects=False)
    assert response.status_code == 302
    location = response.headers.get("location", "")
    assert "accounts.google.com" in location
    assert "client_id=test-client-id" in location


def test_google_callback_returns_503_when_not_configured(client_no_google: TestClient) -> None:
    response = client_no_google.get(
        "/auth/google/callback",
        params={"code": "x", "state": "y"},
    )
    assert response.status_code == 503


def test_google_callback_rejects_invalid_state(client_google_configured: TestClient) -> None:
    response = client_google_configured.get(
        "/auth/google/callback",
        params={"code": "dummy", "state": "not-a-valid-state"},
    )
    assert response.status_code == 400


def test_google_callback_rejects_bad_code(db, client_google_configured: TestClient) -> None:
    from app.services.google_oidc import sign_google_oauth_state

    settings = get_settings()
    state = sign_google_oauth_state(settings.secret_key)

    def override_db():
        yield db

    app.dependency_overrides[get_db] = override_db
    try:
        response = client_google_configured.get(
            "/auth/google/callback",
            params={"code": "invalid-code", "state": state},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 400
