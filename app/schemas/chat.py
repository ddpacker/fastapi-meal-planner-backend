from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel


class ChatMessageBase(BaseModel):
    role: str  # user / assistant / system
    content: str


class ChatMessageCreate(BaseModel):
    content: str


class ChatMessageRead(ChatMessageBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True


class ChatSessionRead(BaseModel):
    id: int
    recipe_id: int
    title: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    messages: List[ChatMessageRead]

    class Config:
        from_attributes = True

