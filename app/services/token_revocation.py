from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.revoked_token import RevokedToken


def is_jti_revoked(db: Session, jti: str) -> bool:
    row = db.execute(select(RevokedToken).where(RevokedToken.jti == jti)).scalar_one_or_none()
    return row is not None


def revoke_jti(db: Session, jti: str, expires_at: datetime) -> None:
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if db.execute(select(RevokedToken).where(RevokedToken.jti == jti)).scalar_one_or_none() is None:
        db.add(RevokedToken(jti=jti, expires_at=expires_at))
        db.commit()
