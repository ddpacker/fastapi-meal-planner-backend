from datetime import datetime
from typing import Annotated, Optional

from pydantic import BaseModel, EmailStr, Field

from app.schemas.user import PreferencesRead


class UserBase(BaseModel):
    email: EmailStr


class UserCreate(UserBase):
    password: Annotated[str, Field(min_length=8, max_length=128)]


class UserRead(UserBase):
    id: int
    created_at: datetime
    preferences: Optional[PreferencesRead] = None

    class Config:
        from_attributes = True


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class TokenPayload(BaseModel):
    sub: str | None = None
    exp: int | None = None
    jti: str | None = None

