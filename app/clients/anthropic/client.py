import logging

from anthropic import Anthropic
from fastapi import HTTPException, status
from pydantic import ValidationError

from app.clients.base import AIClientBase, ChatModifyResult
from app.clients.anthropic.tools import CHAT_MODIFY_TOOL, GENERATE_RECIPES_TOOL
from app.schemas.recipes import RecipeCreate
from app.utils.prompt_templates import chat_modify_prompt, recipe_generation_prompt

logger = logging.getLogger(__name__)


class AnthropicClient(AIClientBase):
    def __init__(self, api_key: str, model: str) -> None:
        self._client = Anthropic(api_key=api_key)
        self._model = model

    def generate_recipes(self, meal_names: list[str]) -> list[RecipeCreate]:
        prompt = recipe_generation_prompt(meal_names)
        message = self._client.messages.create(
            model=self._model,
            max_tokens=4096,
            tools=[GENERATE_RECIPES_TOOL],
            tool_choice={"type": "tool", "name": "submit_recipes"},
            messages=[{"role": "user", "content": prompt}],
        )
        logger.info(
            "generate_recipes model=%s input_tokens=%d output_tokens=%d",
            self._model,
            message.usage.input_tokens,
            message.usage.output_tokens,
        )
        tool_block = next(
            (b for b in message.content if b.type == "tool_use"),
            None,
        )
        if tool_block is None:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="AI did not return a tool result for recipe generation",
            )

        data = tool_block.input
        if not isinstance(data, dict):
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="AI tool result for recipes was not a JSON object",
            )
        recipes_raw = data.get("recipes")
        if not isinstance(recipes_raw, list):
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="AI tool result was missing a 'recipes' array or it was not a list",
            )
        try:
            return [RecipeCreate.model_validate(item) for item in recipes_raw]
        except ValidationError as exc:
            raise HTTPException(
                status_code=422,
                detail=f"AI returned an invalid recipe structure: {exc}",
            ) from exc

    def chat_modify(
        self,
        recipe_json: str,
        history: list[dict],
        user_message: str,
    ) -> ChatModifyResult:
        prompt = chat_modify_prompt(recipe_json, history, user_message)
        message = self._client.messages.create(
            model=self._model,
            max_tokens=2048,
            tools=[CHAT_MODIFY_TOOL],
            tool_choice={"type": "tool", "name": "submit_response"},
            messages=[{"role": "user", "content": prompt}],
        )
        logger.info(
            "chat_modify model=%s input_tokens=%d output_tokens=%d",
            self._model,
            message.usage.input_tokens,
            message.usage.output_tokens,
        )
        tool_block = next(b for b in message.content if b.type == "tool_use")
        data = tool_block.input
        revised_recipe: RecipeCreate | None = None
        if data.get("revised_recipe"):
            try:
                revised_recipe = RecipeCreate.model_validate(data["revised_recipe"])
            except ValidationError:
                revised_recipe = None
        return ChatModifyResult(
            assistant_message=data["assistant_message"],
            revised_recipe=revised_recipe,
        )
