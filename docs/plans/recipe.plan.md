---
name: recipe
overview: >
  Recipe lifecycle — generation, manual creation, AI-assisted refinement via chat, and 
  management endpoints. The Recipe model is the central entity of the app; this plan covers 
  everything from raw CRUD through AI-driven generation and iterative chat refinement.
todos:
  - id: recipe-crud
    content: >
      Core recipe endpoints are already implemented. Verify and harden:
      POST /recipes (manual create with ingredients),
      GET /recipes/{recipe_id} (with ingredients),
      GET /recipes/meals/{meal_id} (recipes linked to a planned meal).
      All use SQLAlchemy 2.0 select() style and filter by current_user.id.
      Ensure 404 is returned (not 403) for recipes belonging to other users.
    status: done

  - id: recipe-generation
    content: >
      POST /meal-plans/{plan_id}/generate-recipes calls recipe_service.generate_recipes_for_plan().
      Service loads planned meal names, calls AIClientBase.generate_recipes(), persists 
      Recipe + RecipeIngredient + PlannedMealRecipe rows, and returns the updated MealPlanWeek.
      Re-generation removes existing links before creating new ones.
    status: done

  - id: recipe-instructions-steps
    content: >
      Refactor instructions from a single Text blob into structured, ordered steps.
      New RecipeStep model (id, recipe_id, step_number, text) with an ordered relationship
      on Recipe. Schemas: RecipeStepBase/Create/Read; Recipe schemas replace instructions:str
      with steps: List[RecipeStepRead]. AI tool schema (clients/anthropic/tools.py) changes
      instructions from {"type":"string"} to an array. chat_service serialize/apply and
      recipe_service persistence updated to read/write steps. Alembic migration moves
      recipes.instructions into recipe_steps rows (split existing text into one step, or by newline).
    status: done
    dependencies:
      - recipe-crud

  - id: ingredient-catalog
    content: >
      Normalize ingredients into a canonical, GLOBAL Ingredient catalog to kill duplication.
      New Ingredient model (id, name UNIQUE normalized, category) shared across all users.
      RecipeIngredient becomes a pure association object: recipe_id, ingredient_id (FK),
      quantity, unit — drop the name/category columns. RecipeIngredientRead nests IngredientRead
      so name/category still surface in responses. New ingredient_service.get_or_create(db, name,
      category) upserts by normalized (lowercased/trimmed) name; used by manual POST /recipes,
      PUT /recipes, and AI persistence in recipe_service. Treat the catalog as append-mostly
      reference data — no per-user rename/delete of shared rows. Alembic migration: create
      ingredients, backfill distinct (name, category) from recipe_ingredients, add ingredient_id
      FK + backfill, then drop name/category. NOTE: GroceryItem repeats the same name/quantity/
      unit/category shape — out of scope here, but the global catalog is meant to back it later.
    status: done
    dependencies:
      - recipe-crud

  - id: recipe-search-and-filter
    content: >
      Add GET /recipes with pagination and filtering so users can browse their recipe library.
      Support query params: search (title contains), source_model (filter by AI model), 
      page + page_size (default 20). Return RecipeRead list (without nested ingredients for 
      performance — use a RecipeSummaryRead schema). Filter by current_user.id.
    status: pending
    dependencies:
      - recipe-crud
      - recipe-instructions-steps
      - ingredient-catalog

  - id: recipe-update-delete
    content: >
      Add PUT /recipes/{recipe_id} for full recipe updates (title, instructions, servings, ingredients)
      and DELETE /recipes/{recipe_id}. 
      PUT replaces the ingredient list (delete existing, insert new) in the same transaction.
      DELETE cascades to RecipeIngredient, NutritionInfo, and PlannedMealRecipe via DB cascade.
      Return 204 for DELETE. Add tests for both.
      PUT replaces both the step list and the ingredient line-items (via ingredient_service
      get-or-create); it does not mutate shared Ingredient catalog rows.
    status: pending
    dependencies:
      - recipe-crud
      - recipe-instructions-steps
      - ingredient-catalog

  - id: recipe-tests
    content: >
      Expand test coverage beyond what exists in test_meal_plans.py and test_recipe_service.py:
      - Router tests for GET /recipes (list/filter), PUT, DELETE
      - Assert DB state (rows created/deleted) not just response shape
      - For AI-linked endpoints (generate, chat), assert FakeClient.recorded_calls
    status: pending
    dependencies:
      - recipe-search-and-filter
      - recipe-update-delete
---

## Roadmap

| Status | Task |
|--------|------|
| ✅ Done | Recipe CRUD (create, get by id, get by meal) |
| ✅ Done | AI recipe generation via generate_recipes_for_plan service |
| ✅ Done | Chat session create/get/send wired to chat_service (see chat.plan.md) |
| ✅ Done | **Refactor:** structured instructions → recipe_steps |
| ✅ Done | **Refactor:** global Ingredient catalog + association RecipeIngredient |
| ⏳ Pending | GET /recipes list endpoint with search + pagination |
| ⏳ Pending | PUT /recipes/{id} and DELETE /recipes/{id} |
| ⏳ Pending | Expanded router + service tests |

---

## Implementation notes

### Models involved
- `Recipe` — id, user_id, title, servings, source_model (instructions now via `RecipeStep`)
- `RecipeStep` — id, recipe_id, step_number, text (ordered; replaces the instructions Text blob)
- `Ingredient` — id, name (unique, normalized), category. **Global/shared catalog**, append-mostly
- `RecipeIngredient` — association object: id, recipe_id, ingredient_id (FK), quantity (Numeric), unit
- `PlannedMealRecipe` — join table linking PlannedMeal ↔ Recipe with a `role` field
- `ChatSession` / `ChatMessage` — linked to recipe_id for refinement history

### Ingredient/step refactor rationale
- Old `RecipeIngredient` fused line-item data (quantity/unit) with ingredient identity
  (name/category), so every recipe re-typed "carrots" — no dedup, no "which recipes use X?",
  typos silently fork the same ingredient. Splitting identity into a global `Ingredient`
  catalog fixes this; the association object carries only per-use quantity/unit.
- `category` is a property of the ingredient (produce/dairy), so it lives on `Ingredient`;
  `unit` is per-use (2 whole vs 100g carrots), so it stays on `RecipeIngredient`.
- Instructions had the opposite problem — under-structured. A single Text blob can't be
  rendered/edited step-by-step, so it becomes ordered `RecipeStep` rows.
- `GroceryItem` still carries the denormalized name/quantity/unit/category shape; the global
  catalog is intended to back it in a later pass (out of scope for this plan).

### Key constraints
- `source_model` is set to the AI model name at generation time; null for manually created recipes
- Re-generation removes `PlannedMealRecipe` links but keeps the `Recipe` rows — they remain
  in the user's recipe library and can still be accessed, chatted with, or manually linked
- Meal plan deletion removes `PlannedMealRecipe` links only; `Recipe` rows are retained
- Recipes are only deleted explicitly by the user (DELETE /recipes/{id}) or when the user
  account itself is deleted (cascade from User)
- Chat revision updates the `Recipe` row in place (same id) — chat history is preserved
- All queries filter by `user_id`; for PlannedMeal-linked resources, join up to MealPlanWeek.user_id

### RecipeSummaryRead schema (for list endpoint)
Fields: id, title, servings, source_model, created_at. Omit steps and ingredients 
to keep list responses light. Full details via GET /recipes/{id}.
