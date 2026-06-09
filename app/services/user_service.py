from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import get_password_hash, verify_password
from app.models.user import User
from app.schemas.user import UserUpdate


def update_user(db: Session, user: User, user_in: UserUpdate) -> User:
    updates = user_in.model_dump(exclude_unset=True, exclude={"current_password"})

    if "email" in updates and updates["email"] != user.email:
        existing = db.execute(select(User).where(User.email == updates["email"])).scalar_one_or_none()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered",
            )
        user.email = updates["email"]

    if "password" in updates:
        if not verify_password(user_in.current_password, user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Incorrect current password",
            )
        user.password_hash = get_password_hash(updates["password"])

    db.commit()
    db.refresh(user)
    return user
