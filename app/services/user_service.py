from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import get_password_hash, verify_password
from app.models.user import User
from app.models.user_preferences import UserPreferences
from app.schemas.user import PreferencesUpdate, UserUpdate


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


def get_or_create_preferences(db: Session, user: User) -> UserPreferences:
    prefs = db.execute(
        select(UserPreferences).where(UserPreferences.user_id == user.id)
    ).scalar_one_or_none()
    if prefs is None:
        prefs = UserPreferences(user_id=user.id)
        db.add(prefs)
        db.commit()
        db.refresh(prefs)
    return prefs


def update_preferences(
    db: Session, user: User, prefs_in: PreferencesUpdate
) -> UserPreferences:
    prefs = get_or_create_preferences(db, user)
    updates = prefs_in.model_dump(exclude_unset=True)
    if "unit_system" in updates:
        prefs.unit_system = updates["unit_system"]
    db.commit()
    db.refresh(prefs)
    return prefs
