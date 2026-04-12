---
name: fastapi-meal-planner-backend
overview: FastAPI + PostgreSQL backend for a weekly meal planning assistant. An abstract AI client layer drives recipe generation and chat refinement. Anthropic is the first concrete provider. No frontend — pure JSON API.
todos:
  - id: setup-fastapi-project
    content: Initialize FastAPI project skeleton with configuration, main app, and basic health endpoint, wired for Postgres and AI provider settings via environment variables.
    status: done

  - id: db-and-models
    content: Set up SQLAlchemy + Alembic with PostgreSQL and implement core models for users, meal plans, recipes, ingredients, grocery lists, chats, and nutrition info.
    status: done
    dependencies:
      - setup-fastapi-project

  - id: schemas-and-routers
    content: Create Pydantic schemas and FastAPI routers for auth, meal plans, recipes, chat, grocery, and nutrition endpoints.
    status: done
    dependencies:
      - db-and-models

  - id: ai-provider-integration
    content: >
      Implement recipe_service and chat_service in app/services/ that depend on the AIClientBase ABC.
      Wire recipe_service into POST /meal-plans/{plan_id}/generate-recipes and chat_service into 
      POST /chat-sessions/{session_id}/messages, replacing the current router stubs.
      See ai-connector.plan.md for ABC, provider implementations, and prompt templates.
    status: pending
    dependencies:
      - schemas-and-routers

  - id: grocery-and-nutrition-services
    content: >
      Extract grocery aggregation logic from app/routers/grocery.py into app/services/grocery_service.py.
      Implement app/services/nutrition_service.py that calls the AI client ABC to estimate per-serving
      macros from ingredient lists, replacing the placeholder NutritionInfo record in
      POST /recipes/{recipe_id}/nutrition. Wire both services into their respective routers.
    status: pending
    dependencies:
      - ai-provider-integration

  - id: tests-and-docs
    content: >
      Add pytest test suite: one file per router (tests/routers/), one per service with non-trivial
      logic (tests/services/). Use in-memory SQLite or a test Postgres DB via DATABASE_URL env override.
      Always inject FakeClient (ABC double) — never make real AI API calls in tests.
      Ensure OpenAPI docs at /docs are clean: correct tags, summaries, and example responses.
    status: pending
    dependencies:
      - grocery-and-nutrition-services
---

## Roadmap

### Backend API

| Status | Task |
|--------|------|
| ✅ Done | Project skeleton, config, and `GET /health` endpoint |
| ✅ Done | SQLAlchemy models and Alembic migrations |
| ✅ Done | Pydantic schemas and all router endpoints (with AI stubs) |
| ✅ Done | Grocery list aggregation logic (in router — needs extraction to service) |
| ⏳ Pending | AI provider ABC + AnthropicClient + FakeClient |
| ⏳  Pending | Nutrition estimation (placeholder record only, no AI integration yet) |
| ⏳ Pending | `recipe_service` and `chat_service` wired to AI client |
| ⏳ Pending | Extract grocery logic to `grocery_service`, implement `nutrition_service` |
| ⏳ Pending | pytest suite + OpenAPI documentation cleanup |

---

## Implementation notes

### What exists today

**`app/core/`**
- `security.py` — JWT encode/decode, `get_password_hash`, `verify_password`
- `deps.py` — `get_current_user` FastAPI dependency

**`app/db/`**
- `base_class.py` — declarative `Base`
- `base.py` — imports all models (used by Alembic `env.py`)
- `session.py` — `engine`, `SessionLocal`, `get_db` dependency

**`app/models/`** — all models implemented with SQLAlchemy 2.0 `Mapped[T]` / `mapped_column` style:
`user`, `meal_plan` (MealPlanWeek, PlannedMeal, PlannedMealRecipe), `recipe` (Recipe, RecipeIngredient), `nutrition` (NutritionInfo), `grocery` (GroceryList, GroceryItem), `chat` (ChatSession, ChatMessage)

**`app/routers/`** — all routers registered:
- `auth` — `POST /auth/register`, `POST /auth/login`
- `meal_plans` — CRUD + `POST /{plan_id}/generate-recipes` (stub — returns plan unchanged)
- `recipes` — `POST`, `GET /{recipe_id}`, `GET /meals/{meal_id}`, nutrition endpoints (placeholder)
- `chat` — create session, get session, `POST /messages` (stub — echoes placeholder assistant message)
- `grocery` — generate list (aggregation implemented inline), get list, patch item

### Known tech debt (fix on next touch)
- All routers use `db.query()` (SQLAlchemy 1.x). Migrate to `select()` + `session.execute()`.
- Schemas in `app/schemas/recipes.py` use `class Config`. Migrate to `model_config = ConfigDict(from_attributes=True)`.