from typing import Annotated, Optional

from pydantic import BaseModel, EmailStr, Field, model_validator


class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    password: Annotated[Optional[str], Field(min_length=8, max_length=128)] = None
    current_password: Optional[str] = None

    @model_validator(mode="after")
    def password_requires_current_password(self) -> "UserUpdate":
        if self.password is not None and self.current_password is None:
            raise ValueError("current_password is required when changing password")
        return self
