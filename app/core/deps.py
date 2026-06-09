from fastapi import Cookie, Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.security import decode_token
from app.db.session import get_db
from app.models.user import User
from app.schemas.auth import TokenPayload
from app.services.token_revocation import is_jti_revoked


def get_current_token_payload(
    db: Session = Depends(get_db),
    access_token: str | None = Cookie(default=None),
    authorization: str | None = Header(default=None),
) -> TokenPayload:
    settings = get_settings()

    if settings.is_development:
        token: str | None = None
        if authorization and authorization.startswith("Bearer "):
            token = authorization.removeprefix("Bearer ")
    else:
        token = access_token

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
        )
    payload = decode_token(token)
    if payload is None or not payload.sub:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
        )
    if payload.jti and is_jti_revoked(db, payload.jti):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
        )
    return payload


def get_current_user(
    db: Session = Depends(get_db),
    payload: TokenPayload = Depends(get_current_token_payload),
) -> User:
    user = db.execute(select(User).where(User.id == int(payload.sub))).scalar_one_or_none()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )
    return user
