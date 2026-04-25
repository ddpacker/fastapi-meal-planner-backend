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

  - id: recipe-search-and-filter
    content: >
      Add GET /recipes with pagination and filtering so users can browse their recipe library.
      Support query params: search (title contains), source_model (filter by AI model), 
      page + page_size (default 20). Return RecipeRead list (without nested ingredients for 
      performance — use a RecipeSummaryRead schema). Filter by current_user.id.
    status: pending
    dependencies:
      - recipe-crud

  - id: recipe-update-delete
    content: >
      Add PUT /recipes/{recipe_id} for full recipe updates (title, instructions, servings, ingredients)
      and DELETE /recipes/{recipe_id}. 
      PUT replaces the ingredient list (delete existing, insert new) in the same transaction.
      DELETE cascades to RecipeIngredient, NutritionInfo, and PlannedMealRecipe via DB cascade.
      Return 204 for DELETE. Add tests for both.
    status: pending
    dependencies:
      - recipe-crud

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
| ⏳ Pending | GET /recipes list endpoint with search + pagination |
| ⏳ Pending | PUT /recipes/{id} and DELETE /recipes/{id} |
| ⏳ Pending | Expanded router + service tests |

---

## Implementation notes

### Models involved
- `Recipe` — id, user_id, title, instructions, servings, source_model
- `RecipeIngredient` — id, recipe_id, name, quantity (Numeric), unit, category
- `PlannedMealRecipe` — join table linking PlannedMeal ↔ Recipe with a `role` field
- `ChatSession` / `ChatMessage` — linked to recipe_id for refinement history

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
Fields: id, title, servings, source_model, created_at. Omit instructions and ingredients 
to keep list responses light. Full details via GET /recipes/{id}.
