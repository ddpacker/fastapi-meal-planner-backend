import json
from dataclasses import dataclass
from pathlib import Path

from app.clients.base import AIClientBase, ChatModifyResult, MealGenerationMeal
from app.models.meal_plan import MealCourseRole
from app.schemas.recipes import RecipeCreate

_FIXTURES_PATH = Path(__file__).parent.parent.parent / "tests" / "fixtures" / "sample_recipes.json"


@dataclass
class RecordedCall:
    method: str
    kwargs: dict


class FakeClient(AIClientBase):
    def __init__(self, chat_revised_recipe: RecipeCreate | None = None) -> None:
        self.recorded_calls: list[RecordedCall] = []
        self._fixtures: list[dict] = json.loads(_FIXTURES_PATH.read_text())
        self._chat_revised_recipe = chat_revised_recipe

    def generate_recipes(self, meals: list[MealGenerationMeal]) -> list[RecipeCreate]:
        self.recorded_calls.append(
            RecordedCall(method="generate_recipes", kwargs={"meals": meals})
        )
        slots: list[tuple[str, MealCourseRole, str | None]] = []
        for meal_name, courses in meals:
            for role, description in courses:
                slots.append((meal_name, role, description))
        recipes: list[RecipeCreate] = []
        for i, (_meal_name, role, _description) in enumerate(slots):
            raw = dict(self._fixtures[i % len(self._fixtures)])
            raw["role"] = role.value
            recipes.append(RecipeCreate.model_validate(raw))
        return recipes

    def chat_modify(
        self,
        recipe_json: str,
        history: list[dict],
        user_message: str,
    ) -> ChatModifyResult:
        self.recorded_calls.append(
            RecordedCall(
                method="chat_modify",
                kwargs={
                    "recipe_json": recipe_json,
                    "history": history,
                    "user_message": user_message,
                },
            )
        )
        return ChatModifyResult(
            assistant_message="Here is your updated recipe.",
            revised_recipe=self._chat_revised_recipe,
        )
