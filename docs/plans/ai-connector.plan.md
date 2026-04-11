---
name: ai-connector
overview: >
  Build a provider-agnostic AI client layer (Python ABC) for the meal planner backend.
  Implement AnthropicClient as the first concrete provider, a FakeClient test double for
  local/test use, prompt templates, and service modules that replace the current router stubs.
todos:
  - id: ai-base-client
    content: >
      Create app/clients/base.py defining an abstract base class AIClientBase with two abstract
      methods: generate_recipes(meal_names: list[str]) -> list[RecipeCreate] and
      chat_modify(recipe: RecipeRead, history: list[dict], user_message: str) -> ChatModifyResult.
      Define shared return types (or import from schemas) used by both methods.
      Services must depend only on this ABC — never on a concrete provider import.
    status: done

  - id: ai-fake-client
    content: >
      Create app/clients/fake.py implementing AIClientBase without any outbound HTTP calls.
      The client must record every call (prompt text, parameters) to an internal list for
      test assertion. generate_recipes returns deterministic fixture recipes loaded from a
      JSON file at tests/fixtures/sample_recipes.json. chat_modify returns a canned
      ChatModifyResult. Used in all pytest tests and local runs where AI_PROVIDER=test.
    status: done
    dependencies:
      - ai-base-client

  - id: ai-anthropic-client
    content: >
      Create app/clients/anthropic_client.py implementing AIClientBase using the anthropic SDK.
      Add anthropic to pyproject.toml via `uv add anthropic`.
      Model name comes from settings.anthropic_model. API key from settings.anthropic_api_key.
      generate_recipes: send the recipe generation prompt, parse structured JSON response into
      list[RecipeCreate] via Pydantic model_validate; raise HTTPException 422 on ValidationError.
      chat_modify: send current recipe JSON + chat history + user message; parse response into
      ChatModifyResult. Log model name and token usage (usage.input_tokens, usage.output_tokens)
      at INFO level — never log prompt/response content.
    status: done
    dependencies:
      - ai-base-client

  - id: prompt-templates
    content: >
      Create app/utils/prompt_templates.py with two functions:
      recipe_generation_prompt(meal_names: list[str]) -> str — instructs the model to return a
      JSON array where each element has: title, servings, instructions (string), ingredients
      (list of {name, quantity, unit, category}), and nutrition_estimate
      ({calories, protein_g, carbs_g, fat_g, per_serving: true}).
      chat_modify_prompt(recipe_json: str, history: list[dict], user_message: str) -> str —
      includes current recipe JSON, chat history, and user request; asks for a conversational
      reply and optionally a revised recipe JSON block when structural changes are requested.
      All prompt strings live here — nowhere else in the codebase.
    status: done
    dependencies:
      - ai-base-client

  - id: client-factory
    content: >
      Add AI_PROVIDER setting to app/config.py (default: "anthropic"; options: "anthropic", "test").
      Add a get_ai_client() factory function (or FastAPI dependency) in app/clients/factory.py
      that reads settings.ai_provider and returns the appropriate AIClientBase instance.
      Services receive the client via dependency injection — never instantiate directly.
    status: pending
    dependencies:
      - ai-anthropic-client
      - ai-fake-client

  - id: recipe-service
    content: >
      Create app/services/recipe_service.py with:
      generate_recipes_for_plan(plan_id: int, db: Session, ai_client: AIClientBase, user: User)
        -> MealPlanWeek — reads PlannedMeal rows for the plan, calls ai_client.generate_recipes()
        with the list of meal_names, creates Recipe + RecipeIngredient rows, links them via
        PlannedMealRecipe, and returns the refreshed MealPlanWeek.
      Wire into POST /meal-plans/{plan_id}/generate-recipes in app/routers/meal_plans.py,
      replacing the current stub that returns the plan unchanged.
    status: pending
    dependencies:
      - client-factory
      - prompt-templates

  - id: chat-service
    content: >
      Create app/services/chat_service.py with:
      send_message(session_id: int, content: str, db: Session, ai_client: AIClientBase, user: User)
        -> list[ChatMessage] — loads the ChatSession and its Recipe, builds message history from
        existing ChatMessage rows, calls ai_client.chat_modify(), persists the assistant ChatMessage,
        optionally updates Recipe/RecipeIngredient rows when the response includes a revised recipe,
        and returns all messages ordered by created_at asc.
      Wire into POST /chat-sessions/{session_id}/messages in app/routers/chat.py,
      replacing the current stub that echoes a placeholder assistant reply.
    status: pending
    dependencies:
      - client-factory
      - prompt-templates

  - id: grocery-service
    content: >
      Extract the ingredient aggregation logic from app/routers/grocery.py into
      app/services/grocery_service.py as:
      generate_grocery_list(plan_id: int, db: Session, user: User) -> GroceryList
      The router's generate_grocery_list endpoint becomes a thin call to the service.
      No AI calls required for this task — aggregation is pure Python logic.
    status: pending
    dependencies:
      - client-factory

  - id: nutrition-service
    content: >
      Create app/services/nutrition_service.py with:
      calculate_nutrition(recipe_id: int, db: Session, ai_client: AIClientBase, user: User)
        -> NutritionInfo — loads Recipe + RecipeIngredient rows, calls ai_client to estimate
        per-serving macros (calories, protein_g, carbs_g, fat_g), validates via NutritionInfoCreate
        schema, upserts NutritionInfo row, returns the result.
      Wire into POST /recipes/{recipe_id}/nutrition in app/routers/recipes.py,
      replacing the current stub that creates an empty placeholder record.
    status: pending
    dependencies:
      - client-factory
      - prompt-templates
---

## Roadmap

### AI connector implementation

| Status | Task | Key files |
|--------|------|-----------|
| ✅ Done | AI client ABC | `app/clients/base.py` |
| ✅ Done | FakeClient (recording test double) | `app/clients/fake.py`, `tests/fixtures/sample_recipes.json` |
| ✅ Done | AnthropicClient (concrete provider) | `app/clients/anthropic_client.py` |
| ✅ Done | Prompt templates | `app/utils/prompt_templates.py` |
| ✅ Done | Client factory + settings wiring | `app/clients/factory.py`, `app/config.py` |
| ⏳ Pending | Recipe service + generate-recipes endpoint | `app/services/recipe_service.py`, `app/routers/meal_plans.py` |
| ⏳ Pending | Chat service + messages endpoint | `app/services/chat_service.py`, `app/routers/chat.py` |
| ⏳ Pending | Extract grocery service | `app/services/grocery_service.py`, `app/routers/grocery.py` |
| ⏳ Pending | Nutrition service + nutrition endpoint | `app/services/nutrition_service.py`, `app/routers/recipes.py` |

---

## Implementation notes

### Recommended build order

Build in dependency order to avoid circular imports and keep tests passing at each step:

1. `ai-base-client` — ABC and shared types
2. `ai-fake-client` — enables testing immediately
3. `prompt-templates` — pure string functions, no deps
4. `ai-anthropic-client` — concrete provider
5. `client-factory` — settings wiring
6. `recipe-service` → wire into `meal_plans` router
7. `chat-service` → wire into `chat` router
8. `grocery-service` → extract from `grocery` router
9. `nutrition-service` → wire into `recipes` router

### ABC contract

```python
# app/clients/base.py
from abc import ABC, abstractmethod
from app.schemas.recipes import RecipeCreate

class ChatModifyResult:
    assistant_message: str
    revised_recipe: RecipeCreate | None  # None if no structural change

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
```

### Required prompt output shapes

**Recipe generation** — model must return a JSON array:
```json
[
  {
    "title": "Chicken Tacos",
    "servings": 4,
    "instructions": "...",
    "ingredients": [
      {"name": "chicken breast", "quantity": 500, "unit": "g", "category": "meat"}
    ],
    "nutrition_estimate": {
      "calories": 450, "protein_g": 35, "carbs_g": 30, "fat_g": 12, "per_serving": true
    }
  }
]
```

**Chat modify** — model must return JSON:
```json
{
  "message": "Sure, I made it vegetarian by swapping chicken for tofu.",
  "revised_recipe": { ... }  // omit key entirely if no structural change
}
```

### Settings additions

Add to `app/config.py`:
```python
ai_provider: str = "anthropic"   # "anthropic" | "test"
```

### Dependency for router injection

```python
# In routers, inject the AI client:
from app.clients.factory import get_ai_client
from app.clients.base import AIClientBase

def my_endpoint(ai_client: AIClientBase = Depends(get_ai_client), ...):
    ...
```

### Testing

- Always use `AI_PROVIDER=test` in tests (or override `get_ai_client` dependency).
- Assert on `fake.recorded_calls` to verify prompt content.
- Use `tests/fixtures/sample_recipes.json` for deterministic recipe payloads.
- Never set `ANTHROPIC_API_KEY` in test environment.
