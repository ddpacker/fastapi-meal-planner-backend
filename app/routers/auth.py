from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse, RedirectResponse
from itsdangerous import BadSignature, SignatureExpired
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.deps import get_current_token_payload, get_current_user
from app.core.security import create_access_token, get_password_hash, verify_password
from app.db.session import get_db
from app.models.user import User
from app.schemas.auth import TokenPayload, UserCreate, UserRead
from app.services.token_revocation import revoke_jti
from app.services.google_oidc import (
    build_google_authorization_url,
    complete_google_login,
    google_oauth_configured,
    sign_google_oauth_state,
    verify_google_oauth_state,
)


router = APIRouter(prefix="/auth", tags=["auth"])


def _token_response(
    *,
    token: str,
    content: dict,
    status_code: int = status.HTTP_200_OK,
) -> JSONResponse:
    settings = get_settings()
    if settings.is_development:
        return JSONResponse(
            status_code=status_code,
            content={**content, "access_token": token, "token_type": "bearer"},
        )
    response = JSONResponse(status_code=status_code, content=content)
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        secure=settings.cookies_secure,
        samesite=settings.cookies_samesite,
    )
    return response


@router.get("/users/me", response_model=UserRead)
def get_me(current_user: User = Depends(get_current_user)) -> User:
    return current_user


@router.post("/register", status_code=status.HTTP_201_CREATED)
def register_user(user_in: UserCreate, db: Session = Depends(get_db)) -> JSONResponse:
    user_in.email = user_in.email.lower()
    existing = db.query(User).filter(User.email == user_in.email).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )
    user = User(email=user_in.email, password_hash=get_password_hash(user_in.password))
    db.add(user)
    db.commit()
    db.refresh(user)

    access_token = create_access_token(subject=str(user.id))
    return _token_response(
        token=access_token,
        content={"id": user.id, "email": user.email},
        status_code=status.HTTP_201_CREATED,
    )


@router.post("/login", status_code=status.HTTP_200_OK)
def login_for_access_token(
    credentials: UserCreate,
    db: Session = Depends(get_db),
) -> JSONResponse:
    credentials.email = credentials.email.lower()
    user = db.query(User).filter(User.email == credentials.email).first()
    if not user or not verify_password(credentials.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )

    access_token = create_access_token(subject=str(user.id))
    return _token_response(token=access_token, content={"message": "ok"})


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    db: Session = Depends(get_db),
    payload: TokenPayload = Depends(get_current_token_payload),
    _user: User = Depends(get_current_user),
) -> None:
    if not payload.jti or payload.exp is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Token cannot be revoked",
        )
    expires_at = datetime.fromtimestamp(payload.exp, tz=timezone.utc)
    revoke_jti(db, payload.jti, expires_at)


@router.get("/google")
def google_login_start() -> RedirectResponse:
    settings = get_settings()
    if not google_oauth_configured(settings):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Google sign-in is not configured",
        )
    state = sign_google_oauth_state(settings.secret_key)
    url = build_google_authorization_url(
        client_id=settings.google_client_id or "",
        redirect_uri=settings.google_redirect_uri or "",
        state=state,
    )
    return RedirectResponse(url=url, status_code=status.HTTP_302_FOUND)


@router.get("/google/callback")
def google_login_callback(
    code: str,
    state: str,
    db: Session = Depends(get_db),
) -> RedirectResponse:
    settings = get_settings()
    if not google_oauth_configured(settings):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Google sign-in is not configured",
        )
    try:
        verify_google_oauth_state(settings.secret_key, state)
    except (BadSignature, SignatureExpired):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired OAuth state",
        ) from None

    try:
        user = complete_google_login(db, settings, code)
    except ValueError as exc:
        code_msg = exc.args[0] if exc.args else ""
        if code_msg == "google_account_mismatch":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="This email is already linked to a different Google account",
            ) from None
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Google sign-in failed",
        ) from None

    access_token = create_access_token(subject=str(user.id))
    redirect_url = f"{settings.frontend_url}/auth/google/callback"
    if settings.is_development:
        return RedirectResponse(
            url=f"{redirect_url}?access_token={access_token}",
            status_code=status.HTTP_302_FOUND,
        )
    response = RedirectResponse(url=redirect_url, status_code=status.HTTP_302_FOUND)
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        secure=settings.cookies_secure,
        samesite=settings.cookies_samesite,
    )
    return response
