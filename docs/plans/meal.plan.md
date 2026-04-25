---
name: meal
overview: >
  Weekly meal planning — creating and managing MealPlanWeek and PlannedMeal entities.
  Covers the full lifecycle from plan creation through recipe assignment and status tracking,
  plus the AI-powered generate-recipes trigger that bridges meal planning and recipe generation.
todos:
  - id: meal-plan-crud
    content: >
      Core meal plan endpoints are implemented:
      POST /meal-plans (create week with up to 7 planned meals),
      GET /meal-plans (list all plans for current user, sorted by start_date desc),
      GET /meal-plans/{plan_id} (single plan with nested planned_meals),
      PUT /meal-plans/{plan_id} (update title and/or meal list).
      All use SQLAlchemy 2.0 select() and filter by current_user.id.
    status: done

  - id: generate-recipes-trigger
    content: >
      POST /meal-plans/{plan_id}/generate-recipes is wired to 
      recipe_service.generate_recipes_for_plan(). This is the bridge between meal planning 
      and recipe generation — it reads planned meal names and delegates to the AI layer.
      Returns the updated MealPlanWeek with recipes linked via PlannedMealRecipe.
    status: done

  - id: meal-course-role-enum
    content: >
      Introduce a MealCourseRole enum (starter, entree, side, dessert) and migrate
      PlannedMealRecipe.role from a plain string to use it.
      Add a courses column (Postgres array or JSON) to PlannedMeal to store which courses
      the user wants for that meal. Default: ["entree"].
      Alembic migration required for both changes.
      Update PlannedMealCreate and PlannedMealRead schemas to include courses.
      Update PlannedMealRecipeRead to use MealCourseRole for role.
    status: pending
    dependencies:
      - meal-plan-crud

  - id: meal-course-generation
    content: >
      Update recipe_service and AIClientBase.generate_recipes() to accept
      (meal_name, courses) pairs instead of just meal_names, so the AI generates one
      recipe per requested course per meal.
      Update recipe_generation_prompt() in prompt_templates.py to include course context
      per meal (e.g. "generate a starter, entree, and dessert for Taco Night").
      Update FakeClient.generate_recipes() and sample_recipes.json fixture to reflect
      the new signature.
    status: pending
    dependencies:
      - meal-course-role-enum

  - id: meal-course-edit
    content: >
      When a user edits the courses list on an existing PlannedMeal via
      PATCH /meal-plans/{plan_id}/meals/{meal_id}:
      - Removed course: delete the PlannedMealRecipe row for that role (and orphaned Recipe).
      - Added course: call recipe_service.generate_recipe_for_course(planned_meal, role)
        to generate a single new recipe for that slot without touching existing recipes.
      - Changed course (remove + add): treat as the two operations above in sequence.
      generate_recipe_for_course() is a new focused path in recipe_service alongside the
      existing full-plan generation.
    status: pending
    dependencies:
      - meal-course-generation
      - planned-meal-status

  - id: planned-meal-status
    content: >
      Add PATCH /meal-plans/{plan_id}/meals/{meal_id} to update a single PlannedMeal's 
      status (draft → planned) and/or meal_name. Useful when users want to rename a meal 
      slot or mark it as confirmed after reviewing generated recipes.
      Verify the meal belongs to the plan, and the plan belongs to current_user.
      Return the updated PlannedMealRead.
    status: pending
    dependencies:
      - meal-plan-crud

  - id: meal-plan-delete
    content: >
      Add DELETE /meal-plans/{plan_id}.
      Cascade via DB relationships should handle PlannedMeal, PlannedMealRecipe, and 
      GroceryList rows. Verify cascade config on MealPlanWeek model. Return 204.
      Add a test that confirms related rows are removed.
    status: pending
    dependencies:
      - meal-plan-crud

  - id: meal-plan-summary
    content: >
      Extend MealPlanWeekRead (or add a MealPlanWeekSummaryRead) to include a count of 
      planned meals and whether a grocery list exists for this plan. This gives the frontend 
      enough context to render a plan card without needing separate requests.
      Computed fields (not DB columns): meal_count: int, has_grocery_list: bool.
    status: pending
    dependencies:
      - meal-plan-crud

  - id: meal-plan-tests
    content: >
      Existing tests in test_meal_plans.py cover create, list, get, update, and generate-recipes.
      Add tests for:
      - PATCH /meal-plans/{plan_id}/meals/{meal_id} (rename, status change, 404 cross-user)
      - DELETE /meal-plans/{plan_id} (cascade verification)
      - MealPlanWeekSummaryRead fields (meal_count, has_grocery_list)
    status: pending
    dependencies:
      - planned-meal-status
      - meal-plan-delete
      - meal-plan-summary
---

## Roadmap

| Status | Task |
|--------|------|
| ✅ Done | MealPlanWeek + PlannedMeal CRUD (create, list, get, update) |
| ✅ Done | POST /generate-recipes trigger wired to recipe_service |
| ⏳ Pending | MealCourseRole enum + courses column on PlannedMeal + migration |
| ⏳ Pending | Update generate_recipes() signature + prompt for per-course generation |
| ⏳ Pending | Course edit: add/remove single course recipes without full regeneration |
| ⏳ Pending | PATCH individual PlannedMeal (status + name) |
| ⏳ Pending | DELETE /meal-plans/{id} with cascade verification |
| ⏳ Pending | MealPlanWeekRead summary fields (meal_count, has_grocery_list) |
| ⏳ Pending | Expanded tests for new endpoints |

---

## Implementation notes

### Models involved
- `MealPlanWeek` — id, user_id, start_date, end_date, title; cascades to PlannedMeal + GroceryList
- `PlannedMeal` — id, meal_plan_week_id, day_index (0–6), meal_name, status (draft/planned), courses (array, default ["entree"])
- `PlannedMealRecipe` — join table with role (MealCourseRole enum); links PlannedMeal ↔ Recipe

### PlannedMeal status enum
Current values: `draft`, `planned`. Consider `skipped` as a future value for days the user 
wants to omit from grocery generation.

### day_index convention
0 = Monday … 6 = Sunday. Enforced at schema level (ge=0, le=6). No gaps allowed in a plan 
(frontend should send all 7 or a contiguous subset).

### Summary field implementation
Compute `meal_count` and `has_grocery_list` in the router via subquery or Python len() after 
eager-loading relationships. Don't add DB columns — these are derived properties.

### Authorization pattern
For PATCH /meals/{meal_id}: query PlannedMeal, then verify 
`planned_meal.meal_plan_week.user_id == current_user.id`. Return 404 if not found or 
if user mismatch (don't leak existence).
