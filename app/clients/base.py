from abc import ABC, abstractmethod
from typing import TypeAlias

from pydantic import BaseModel

from app.models.meal_plan import MealCourseRole
from app.schemas.recipes import RecipeCreate

MealGenerationCourse: TypeAlias = tuple[MealCourseRole, str | None]
MealGenerationMeal: TypeAlias = tuple[str, list[MealGenerationCourse]]


class ChatModifyResult(BaseModel):
    assistant_message: str
    revised_recipe: RecipeCreate | None = None


class AIClientBase(ABC):
    @abstractmethod
    def generate_recipes(self, meals: list[MealGenerationMeal]) -> list[RecipeCreate]: ...

    @abstractmethod
    def chat_modify(
        self,
        recipe_json: str,
        history: list[dict],  # [{"role": "user"|"assistant", "content": str}]
        user_message: str,
    ) -> ChatModifyResult: ...
