from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.models.user_preferences import UserPreferences
from app.schemas.auth import UserRead
from app.schemas.user import PreferencesRead, PreferencesUpdate, UserUpdate
from app.services.user_service import (
    get_or_create_preferences,
    update_preferences,
    update_user,
)


router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserRead)
def get_current_user_profile(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> UserRead:
    prefs = get_or_create_preferences(db, current_user)
    return UserRead(
        id=current_user.id,
        email=current_user.email,
        created_at=current_user.created_at,
        preferences=PreferencesRead.model_validate(prefs),
    )


@router.patch("/me", response_model=UserRead)
def update_current_user_profile(
    user_in: UserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> User:
    return update_user(db, current_user, user_in)


@router.get("/me/preferences", response_model=PreferencesRead)
def get_current_user_preferences(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> UserPreferences:
    return get_or_create_preferences(db, current_user)


@router.patch("/me/preferences", response_model=PreferencesRead)
def update_current_user_preferences(
    prefs_in: PreferencesUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> UserPreferences:
    return update_preferences(db, current_user, prefs_in)
