from abc import ABC, abstractmethod

from pydantic import BaseModel

from app.schemas.recipes import RecipeCreate


class ChatModifyResult(BaseModel):
    assistant_message: str
    revised_recipe: RecipeCreate | None = None


class AIClientBase(ABC):
    @abstractmethod
    def generate_recipes(self, meal_names: list[str]) -> list[RecipeCreate]: ...

    @abstractmethod
    def chat_modify(
        self,
        recipe_json: str,
        history: list[dict],  # [{"role": "user"|"assistant", "content": str}]
        user_message: str,
    ) -> ChatModifyResult: ...
