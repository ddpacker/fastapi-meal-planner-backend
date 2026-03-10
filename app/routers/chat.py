from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.db.session import get_db
from app.models.chat import ChatMessage, ChatSession
from app.models.recipe import Recipe
from app.models.user import User
from app.schemas.chat import ChatMessageCreate, ChatMessageRead, ChatSessionRead


router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("/recipes/{recipe_id}/chat-sessions", response_model=ChatSessionRead, status_code=status.HTTP_201_CREATED)
def create_chat_session_for_recipe(
    recipe_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ChatSession:
    recipe = (
        db.query(Recipe)
        .filter(Recipe.id == recipe_id, Recipe.user_id == current_user.id)
        .first()
    )
    if not recipe:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recipe not found")

    session = ChatSession(recipe_id=recipe.id, user_id=current_user.id, title=recipe.title)
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


@router.get("/chat-sessions/{session_id}", response_model=ChatSessionRead)
def get_chat_session(
    session_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ChatSession:
    session = (
        db.query(ChatSession)
        .filter(ChatSession.id == session_id, ChatSession.user_id == current_user.id)
        .first()
    )
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat session not found")
    return session


@router.post("/chat-sessions/{session_id}/messages", response_model=List[ChatMessageRead])
def send_chat_message(
    session_id: int,
    message_in: ChatMessageCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[ChatMessage]:
    session = (
        db.query(ChatSession)
        .filter(ChatSession.id == session_id, ChatSession.user_id == current_user.id)
        .first()
    )
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat session not found")

    # Save user message
    user_msg = ChatMessage(
        chat_session_id=session.id,
        role="user",
        content=message_in.content,
    )
    db.add(user_msg)

    # TODO: Call Anthropic with current recipe + history and save assistant response.
    # For now, we just echo a stub assistant reply.
    assistant_msg = ChatMessage(
        chat_session_id=session.id,
        role="assistant",
        content="This is a placeholder response. AI integration is not yet implemented.",
    )
    db.add(assistant_msg)

    db.commit()

    messages = (
        db.query(ChatMessage)
        .filter(ChatMessage.chat_session_id == session.id)
        .order_by(ChatMessage.created_at.asc())
        .all()
    )
    return messages

