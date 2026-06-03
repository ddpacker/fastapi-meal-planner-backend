import secrets
from urllib.parse import urlencode

import httpx
from itsdangerous import URLSafeTimedSerializer
from jose import JWTError, jwt
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import Settings
from app.core.security import get_password_hash
from app.models.user import User

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_JWKS_URL = "https://www.googleapis.com/oauth2/v3/certs"
GOOGLE_ISSUERS = ("https://accounts.google.com", "accounts.google.com")
_OAUTH_STATE_SALT = "google-oauth-state-v1"
_OAUTH_STATE_MAX_AGE_SEC = 600


def sign_google_oauth_state(secret_key: str) -> str:
    serializer = URLSafeTimedSerializer(secret_key, salt=_OAUTH_STATE_SALT)
    return serializer.dumps({"n": secrets.token_hex(16)})


def verify_google_oauth_state(secret_key: str, state: str) -> None:
    serializer = URLSafeTimedSerializer(secret_key, salt=_OAUTH_STATE_SALT)
    serializer.loads(state, max_age=_OAUTH_STATE_MAX_AGE_SEC)


def google_oauth_configured(settings: Settings) -> bool:
    return bool(
        settings.google_client_id
        and settings.google_client_secret
        and settings.google_redirect_uri
    )


def build_google_authorization_url(*, client_id: str, redirect_uri: str, state: str) -> str:
    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
        "access_type": "online",
        "prompt": "select_account",
    }
    return f"{GOOGLE_AUTH_URL}?{urlencode(params)}"


def exchange_authorization_code(code: str, settings: Settings) -> dict:
    with httpx.Client(timeout=30.0) as client:
        response = client.post(
            GOOGLE_TOKEN_URL,
            data={
                "code": code,
                "client_id": settings.google_client_id,
                "client_secret": settings.google_client_secret,
                "redirect_uri": settings.google_redirect_uri,
                "grant_type": "authorization_code",
            },
        )
        response.raise_for_status()
        return response.json()


def verify_google_id_token(id_token: str, client_id: str) -> dict:
    with httpx.Client(timeout=30.0) as client:
        jwks_response = client.get(GOOGLE_JWKS_URL)
        jwks_response.raise_for_status()
        jwks = jwks_response.json()

    claims = jwt.decode(
        id_token,
        jwks,
        algorithms=["RS256"],
        audience=client_id,
        issuer=GOOGLE_ISSUERS,
        options={"verify_at_hash": False},
    )
    return claims


def _email_verified(claims: dict) -> bool:
    v = claims.get("email_verified")
    if v is True:
        return True
    if isinstance(v, str) and v.lower() == "true":
        return True
    return False


def upsert_user_from_google(db: Session, *, google_sub: str, email: str) -> User:
    by_sub = db.execute(select(User).where(User.google_sub == google_sub)).scalar_one_or_none()
    if by_sub:
        return by_sub

    by_email = db.execute(
        select(User).where(func.lower(User.email) == email.lower())
    ).scalar_one_or_none()
    if by_email:
        if by_email.google_sub is not None and by_email.google_sub != google_sub:
            raise ValueError("google_account_mismatch")
        by_email.google_sub = google_sub
        db.commit()
        db.refresh(by_email)
        return by_email

    placeholder_password = get_password_hash(secrets.token_urlsafe(32))
    user = User(email=email, password_hash=placeholder_password, google_sub=google_sub)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def complete_google_login(db: Session, settings: Settings, code: str) -> User:
    try:
        token_payload = exchange_authorization_code(code, settings)
    except httpx.HTTPStatusError:
        raise ValueError("token_exchange_failed") from None

    id_token = token_payload.get("id_token")
    if not id_token or not isinstance(id_token, str):
        raise ValueError("missing_id_token")

    try:
        claims = verify_google_id_token(id_token, settings.google_client_id or "")
    except JWTError as exc:
        raise ValueError("invalid_id_token") from exc

    email = claims.get("email").lower()
    sub = claims.get("sub")
    if not email or not sub or not isinstance(email, str) or not isinstance(sub, str):
        raise ValueError("missing_claims")
    if not _email_verified(claims):
        raise ValueError("email_not_verified")

    return upsert_user_from_google(db, google_sub=sub, email=email)
