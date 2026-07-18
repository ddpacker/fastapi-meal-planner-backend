import json

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.clients.base import AIClientBase
from app.models.chat import ChatMessage, ChatSession
from app.models.recipe import Recipe, RecipeIngredient, RecipeStep
from app.models.user import User
from app.schemas.recipes import RecipeCreate, RecipeRead


def send_message(
    session_id: int,
    content: str,
    db: Session,
    ai_client: AIClientBase,
    user: User,
) -> list[ChatMessage]:
    session = db.execute(
        select(ChatSession)
        .where(ChatSession.id == session_id, ChatSession.user_id == user.id)
        .options(
            selectinload(ChatSession.recipe).selectinload(Recipe.steps),
            selectinload(ChatSession.recipe).selectinload(Recipe.ingredients),
            selectinload(ChatSession.recipe).selectinload(Recipe.nutrition_info),
        )
    ).scalar_one_or_none()
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat session not found")

    recipe = session.recipe

    prior_messages = db.execute(
        select(ChatMessage)
        .where(ChatMessage.chat_session_id == session.id)
        .order_by(ChatMessage.created_at.asc())
    ).scalars().all()

    history = [{"role": m.role, "content": m.content} for m in prior_messages]

    user_msg = ChatMessage(
        chat_session_id=session.id,
        role="user",
        content=content,
    )
    db.add(user_msg)
    db.flush()

    recipe_json = _recipe_to_json(recipe)
    result = ai_client.chat_modify(recipe_json, history, content)

    assistant_msg = ChatMessage(
        chat_session_id=session.id,
        role="assistant",
        content=result.assistant_message,
    )
    db.add(assistant_msg)

    if result.revised_recipe is not None:
        _apply_revised_recipe(db, recipe, result.revised_recipe)

    db.commit()

    return list(
        db.execute(
            select(ChatMessage)
            .where(ChatMessage.chat_session_id == session.id)
            .order_by(ChatMessage.created_at.asc())
        ).scalars().all()
    )


def _recipe_to_json(recipe: Recipe) -> str:
    """Serialize recipe for the model — title, steps, servings, ingredients."""
    read = RecipeRead.model_validate(recipe)
    return json.dumps(read.model_dump(mode="json"))


def _apply_revised_recipe(db: Session, recipe: Recipe, revised: RecipeCreate) -> None:
    recipe.title = revised.title
    recipe.servings = revised.servings

    for step in list(recipe.steps):
        db.delete(step)
    for ing in list(recipe.ingredients):
        db.delete(ing)
    db.flush()

    for step in revised.steps:
        db.add(
            RecipeStep(
                recipe_id=recipe.id,
                step_number=step.step_number,
                text=step.text,
            )
        )

    for ing in revised.ingredients:
        db.add(
            RecipeIngredient(
                recipe_id=recipe.id,
                name=ing.name,
                quantity=ing.quantity,
                unit=ing.unit,
                category=ing.category,
            )
        )

    if recipe.nutrition_info is not None:
        db.delete(recipe.nutrition_info)
