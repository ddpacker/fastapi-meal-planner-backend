import json

import pytest
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.clients.fake import FakeClient
from app.models.chat import ChatMessage, ChatSession
from app.models.nutrition import NutritionInfo
from app.models.recipe import Recipe, RecipeIngredient
from app.models.user import User
from app.schemas.recipes import RecipeCreate, RecipeIngredientCreate
from app.services.chat_service import send_message


@pytest.fixture()
def recipe_session(db: Session, user: User) -> tuple[Recipe, ChatSession]:
    recipe = Recipe(
        user_id=user.id,
        title="Chicken Tacos",
        instructions="Cook thoroughly.",
        servings=4,
        source_model="test",
    )
    db.add(recipe)
    db.flush()
    db.add(
        RecipeIngredient(
            recipe_id=recipe.id,
            name="chicken breast",
            quantity=500,
            unit="g",
            category="meat",
        )
    )
    db.add(
        NutritionInfo(
            recipe_id=recipe.id,
            calories=450,
            protein_g=35,
            carbs_g=30,
            fat_g=12,
            per_serving=True,
            source="legacy",
        )
    )
    db.flush()
    chat = ChatSession(recipe_id=recipe.id, user_id=user.id, title=recipe.title)
    db.add(chat)
    db.commit()
    db.refresh(recipe)
    db.refresh(chat)
    return recipe, chat


class TestSendMessage:
    def test_recipe_json_has_no_nutrition_sent_to_model(
        self, db: Session, user: User, recipe_session: tuple[Recipe, ChatSession]
    ):
        _recipe, chat = recipe_session
        client = FakeClient()

        send_message(chat.id, "Make it spicier", db, client, user)

        payload = json.loads(client.recorded_calls[0].kwargs["recipe_json"])
        assert "nutrition_estimate" not in payload
        assert payload["title"] == "Chicken Tacos"
        assert payload["instructions"] == "Cook thoroughly."

    def test_history_excludes_current_message_includes_prior_turns(
        self, db: Session, user: User, recipe_session: tuple[Recipe, ChatSession]
    ):
        _recipe, chat = recipe_session
        db.add_all(
            [
                ChatMessage(chat_session_id=chat.id, role="user", content="First question"),
                ChatMessage(chat_session_id=chat.id, role="assistant", content="First answer"),
            ]
        )
        db.commit()

        client = FakeClient()
        send_message(chat.id, "Follow-up", db, client, user)

        assert client.recorded_calls[0].kwargs["history"] == [
            {"role": "user", "content": "First question"},
            {"role": "assistant", "content": "First answer"},
        ]

    def test_persists_user_and_assistant_messages(
        self, db: Session, user: User, recipe_session: tuple[Recipe, ChatSession]
    ):
        _recipe, chat = recipe_session
        client = FakeClient()

        messages = send_message(chat.id, "Hello", db, client, user)

        assert len(messages) == 2
        assert messages[0].role == "user" and messages[0].content == "Hello"
        assert messages[1].role == "assistant"
        assert messages[1].content == "Here is your updated recipe."

    def test_revised_recipe_updates_recipe_and_ingredients_and_clears_stale_nutrition(
        self, db: Session, user: User, recipe_session: tuple[Recipe, ChatSession]
    ):
        recipe, chat = recipe_session
        revised = RecipeCreate(
            title="Tofu Tacos",
            instructions="Pan fry tofu.",
            servings=2,
            ingredients=[
                RecipeIngredientCreate(
                    name="tofu",
                    quantity=200,
                    unit="g",
                    category="protein",
                )
            ],
        )
        client = FakeClient(chat_revised_recipe=revised)

        send_message(chat.id, "Make it vegetarian", db, client, user)

        db.refresh(recipe)
        assert recipe.title == "Tofu Tacos"
        assert recipe.servings == 2
        ings = list(recipe.ingredients)
        assert len(ings) == 1
        assert ings[0].name == "tofu"
        assert (
            db.execute(
                select(NutritionInfo).where(NutritionInfo.recipe_id == recipe.id)
            ).scalar_one_or_none()
            is None
        )

    def test_unknown_session_raises_404(self, db: Session, user: User):
        client = FakeClient()
        with pytest.raises(HTTPException) as exc:
            send_message(99999, "Hi", db, client, user)
        assert exc.value.status_code == 404
