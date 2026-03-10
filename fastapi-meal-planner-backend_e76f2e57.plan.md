---
name: fastapi-meal-planner-backend
overview: Design a FastAPI backend that integrates with Anthropic to generate weekly recipes, grocery lists, and nutrition estimates, using PostgreSQL for persistence and leaving the frontend (Angular or others) decoupled.
todos:
  - id: setup-fastapi-project
    content: Initialize FastAPI project skeleton with configuration, main app, and basic health endpoint, wired for Anthropic and Postgres settings via environment variables.
    status: pending
  - id: db-and-models
    content: Set up SQLAlchemy + Alembic with PostgreSQL and implement core models for users, meal plans, recipes, ingredients, grocery lists, chats, and nutrition info.
    status: pending
    dependencies:
      - setup-fastapi-project
  - id: schemas-and-routers
    content: Create Pydantic schemas and FastAPI routers for auth, meal plans, recipes, chat, grocery lists, and nutrition endpoints based on the designed API.
    status: pending
    dependencies:
      - db-and-models
  - id: anthropic-integration
    content: Implement Anthropic client wrapper, prompt templates, and services for recipe generation and chat-based recipe modifications, including parsing/validation of structured outputs.
    status: pending
    dependencies:
      - schemas-and-routers
  - id: grocery-and-nutrition-services
    content: Implement grocery list aggregation and nutrition estimation services and wire them into the corresponding endpoints.
    status: pending
    dependencies:
      - anthropic-integration
  - id: tests-and-docs
    content: Add tests for key services and endpoints, ensure automatic docs (OpenAPI/Swagger) look good, and document how a frontend (e.g., Angular) should integrate with the API.
    status: pending
    dependencies:
      - grocery-and-nutrition-services
---

## FastAPI Meal Planner Backend (Anthropic + Postgres)

### 1. High-level architecture

- **Goal**: A backend API that lets a client (Angular/web/mobile) manage a weekly meal plan (7 meals), call Anthropic to generate recipes, support per-meal chat refinement, and then produce a grocery list and approximate nutrition for each recipe.
- **Core pieces**:
  - `FastAPI` app exposing JSON endpoints.
  - `PostgreSQL` as the main database.
  - `SQLAlchemy` + `Alembic` for ORM and migrations.
  - An `Anthropic` client wrapper module for AI calls.
  - Service layer modules for meal planning, recipe generation, grocery list building, and nutrition estimation.
```mermaid
flowchart TD
  client[ClientApp] --> api[FastAPI]
  api --> authService[auth_service]
  api --> mealService[meal_plan_service]
  api --> recipeService[recipe_service]
  api --> chatService[chat_service]
  api --> groceryService[grocery_service]
  api --> nutritionService[nutrition_service]

  mealService --> db[(PostgreSQL)]
  recipeService --> db
  chatService --> db
  groceryService --> db
  nutritionService --> db

  recipeService --> anthropicClient[anthropic_client]
  chatService --> anthropicClient
```


### 2. Project & module structure

- **Top-level layout** (example):
  - `app/main.py` – FastAPI app, routers include, startup/shutdown.
  - `app/config.py` – settings (DB URL, Anthropic API key, model name, etc.).
  - `app/db/session.py` – SQLAlchemy engine, sessionmaker, dependency.
  - `app/db/base.py` – Base class and model imports.
  - `app/models/` – SQLAlchemy models (`user.py`, `meal_plan.py`, `recipe.py`, `ingredient.py`, `chat.py`).
  - `app/schemas/` – Pydantic models for requests/responses.
  - `app/routers/` – FastAPI routers (`meals.py`, `recipes.py`, `chat.py`, `grocery.py`, `auth.py`).
  - `app/services/` – business logic (`meal_plan_service.py`, `recipe_service.py`, `grocery_service.py`, `nutrition_service.py`).
  - `app/clients/anthropic_client.py` – thin wrapper around Anthropic HTTP/SDK.
  - `app/utils/` – shared helpers (e.g., prompt templates, parsing utilities).
  - `alembic/` – migration environment and versions.

### 3. Data model design (Postgres via SQLAlchemy)

- **Users** (`User`)
  - Fields: `id`, `email`, `password_hash`, timestamps.
  - For now, simple email+password; later can plug in OAuth/identity provider.

- **Meal planning & recipes**
  - `MealPlanWeek` – a weekly plan per user.
    - Fields: `id`, `user_id`, `start_date`, `end_date`, `title`, timestamps.
  - `PlannedMeal` – one of the 7 meals in the week.
    - Fields: `id`, `meal_plan_week_id`, `day_index` (0–6), `meal_name` (e.g., "Chicken Tacos"), `status` (draft/final), timestamps.
  - `Recipe` – a recipe owned by a `User`, reusable across multiple meal plans.
    - Fields: `id`, `user_id`, `title`, `instructions` (text/JSON blocks), `servings`, `source_model`, timestamps.
  - `PlannedMealRecipe` – join table linking a `PlannedMeal` to one or more `Recipe` rows.
    - Fields: `id`, `planned_meal_id`, `recipe_id`, `role` (e.g. entree/side).
    - A `PlannedMeal` can have multiple recipes; a `Recipe` can appear in multiple planned meals.

- **Ingredients & grocery items**
  - `RecipeIngredient`
    - Fields: `id`, `recipe_id`, `name`, `quantity`, `unit`, optional `category` (produce/dairy/etc.).
  - `GroceryList` – per-week grocery aggregation.
    - Fields: `id`, `meal_plan_week_id`, `title`, `notes`, timestamps.
  - `GroceryItem`
    - Fields: `id`, `grocery_list_id`, `name`, `total_quantity`, `unit`, `category`, `checked`.

- **Chat & AI interactions**
  - `ChatSession`
    - Fields: `id`, `recipe_id` (or `planned_meal_id`), `user_id`, `title`, timestamps.
  - `ChatMessage`
    - Fields: `id`, `chat_session_id`, `role` (user/assistant/system), `content`, `created_at`.

- **Nutrition estimates**
  - `NutritionInfo`
    - Fields: `id`, `recipe_id`, macro breakdown (`calories`, `protein_g`, `carbs_g`, `fat_g`, etc.), `per_serving` flag.

### 4. API endpoint design

- **Auth endpoints** (`/auth` router)
  - `POST /auth/register` – create user (basic email/password for now).
  - `POST /auth/login` – return JWT (or similar) for authenticated requests.

- **Meal plan & recipe endpoints** (`/meal-plans`, `/recipes` routers)
  - `POST /meal-plans` – create a new weekly meal plan (optionally send the 7 meal names).
  - `GET /meal-plans` – list user’s meal plans.
  - `GET /meal-plans/{plan_id}` – get one plan with its 7 `PlannedMeal` entries.
  - `PUT /meal-plans/{plan_id}` – update plan metadata or meal names.
  - `POST /meal-plans/{plan_id}/generate-recipes` – call Anthropic to generate a recipe for each planned meal (7 calls or a batched call); store `Recipe` + `RecipeIngredient` rows.
  - `GET /meals/{meal_id}/recipe` – get the generated recipe + nutrition, if available.

- **Chat endpoints** (`/chat` router)
  - `POST /recipes/{recipe_id}/chat-sessions` – create a new chat session for refining a recipe.
  - `GET /chat-sessions/{session_id}` – retrieve chat history.
  - `POST /chat-sessions/{session_id}/messages` – send a user message with a requested modification; call Anthropic, save assistant message, and (optionally) update the underlying `Recipe`/`RecipeIngredient`.

- **Grocery list endpoints** (`/grocery` router)
  - `POST /meal-plans/{plan_id}/grocery-list` – generate grocery list from all `RecipeIngredient` rows (aggregate by name+unit, categorize, store `GroceryList` + `GroceryItem`).
  - `GET /grocery-lists/{list_id}` – get the grocery list.
  - `PATCH /grocery-items/{item_id}` – toggle `checked` or adjust quantities.

- **Nutrition endpoints** (`/nutrition` router) – or folded into recipe endpoints
  - `POST /recipes/{recipe_id}/nutrition` – calculate or refresh nutrition info for a recipe (via AI and/or external API).
  - `GET /recipes/{recipe_id}/nutrition` – fetch stored `NutritionInfo`.

### 5. Anthropic integration & prompt strategy

- **Anthropic client wrapper** (`app/clients/anthropic_client.py`)
  - Encapsulate API key handling, base URL, and model name.
  - Expose high-level methods like:
    - `generate_recipes_for_meals(meals: List[PlannedMeal]) -> List[RecipeDraft]`.
    - `chat_recipe_modification(history: List[ChatMessage], user_prompt: str) -> ChatResponse`.

- **Prompt templates** (`app/utils/prompt_templates.py`)
  - **Recipe generation prompt**: instruct model to output structured JSON for each meal:
    - title, servings, ingredients (name, quantity, unit, category), steps, and basic nutrition estimates.
  - **Chat modification prompt**: include current recipe JSON + chat history, ask the model to:
    - answer conversationally, and
    - optionally return a new revised recipe JSON when structural changes are requested (e.g., "make this vegetarian").

- **Parsing & validation**
  - Deserialize the model’s structured output into Pydantic schemas (e.g., `RecipeCreate`, `RecipeIngredientCreate`, `NutritionInfoCreate`).
  - Validate before persisting to Postgres; handle errors gracefully (e.g., fallback to partial results or ask the client to re-try).

### 6. Grocery list & nutrition logic

- **Grocery list generation** (`app/services/grocery_service.py`)
  - Query all `RecipeIngredient` records for a given `MealPlanWeek`.
  - Normalize ingredient names (e.g., case, pluralization basic rules) and units where possible.
  - Aggregate quantities by `(name, unit)` and classify into categories (e.g., by a small static mapping table or AI-assisted classification).
  - Persist `GroceryList` + `GroceryItem` records.

- **Nutrition estimation** (`app/services/nutrition_service.py`)
  - **Phase 1**: Ask Anthropic to approximate per-serving macro nutrients from the recipe ingredient list and steps; parse into `NutritionInfo`.
  - **Phase 2 (optional)**: Integrate with a dedicated nutrition API (e.g., USDA, Edamam) for more precise data and store results in the same `NutritionInfo` model.

### 7. Auth, security, and multi-user concerns

- Implement simple JWT-based auth for now (e.g., `Authorization: Bearer <token>`):
  - `User` table with hashed passwords (e.g., `passlib`).
  - Dependency to resolve `current_user` from the token.
  - All meal/recipe/chat/grocery endpoints require `current_user` and filter data by `user_id`.
- Ensure Anthropic API key and DB URL are taken from environment variables and not hard-coded.

### 8. Testing & observability

- **Testing**
  - Use `pytest` + `httpx` test client for FastAPI endpoints.
  - Mock Anthropic client in tests to avoid real API calls.
  - Include tests for:
    - recipe generation service (with fake AI response),
    - grocery aggregation logic,
    - nutrition parsing and storage,
    - auth-protected endpoints.

- **Logging & monitoring**
  - Configure structured logging (request IDs, user IDs where applicable).
  - Log Anthropic request/response metadata (not full content) for debugging.

### 9. Deployment considerations

- **Containerization**
  - Dockerfile with a production server (e.g., Uvicorn + Gunicorn) and environment-based config.
- **Database**
  - Use Postgres locally (Docker or local install) and run `alembic` migrations on deploy.
- **Frontend-agnostic API**
  - Keep responses clean and JSON-based, suitable for an Angular SPA, React, or mobile app.

This plan focuses solely on the **FastAPI + Postgres backend**, leaving the frontend flexible so you can later plug in Angular or another client.