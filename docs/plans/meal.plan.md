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
      Replace the courses array column on PlannedMeal with a PlannedMealCourse table:
        id, planned_meal_id, role (MealCourseRole), description (str, nullable).
      description is an optional free-text hint per course (e.g. "Bourbon Apple Pork Chop").
      The AI uses it to guide generation for that slot; null means AI decides freely.
      Default behavior: one PlannedMealCourse row with role=entree and description=null.
      Alembic migration required.
      Update PlannedMealCreate to accept a list of PlannedMealCourseCreate
        (role, description). Update PlannedMealRead to include nested PlannedMealCourseRead.
      Update PlannedMealRecipeRead to use MealCourseRole for role.
    status: done
    dependencies:
      - meal-plan-crud

  - id: meal-course-generation
    content: >
      Update recipe_service and AIClientBase.generate_recipes() to accept
      (meal_name, courses) pairs where each course carries its role and optional description,
      so the AI generates one recipe per course per meal, guided by the description when present.
      Update recipe_generation_prompt() in prompt_templates.py to include course context per meal
      (e.g. "generate an entree for Pork Night: Bourbon Apple Marinaded Pork Chop, and a side").
      When description is null for a course, let the AI decide freely based on the meal name.
      Update FakeClient.generate_recipes() and sample_recipes.json fixture to reflect
      the new signature.
    status: done
    dependencies:
      - meal-course-role-enum

  - id: meal-course-edit
    content: >
      When a user edits courses on an existing PlannedMeal via
      PATCH /meal-plans/{plan_id}/meals/{meal_id}:
      - Removed course: delete the PlannedMealCourse row, the linked PlannedMealRecipe, and
        the orphaned Recipe.
      - Added course: insert a PlannedMealCourse row (role + optional description), then call
        recipe_service.generate_recipe_for_course(planned_meal, course) to generate one recipe
        for that slot without touching existing courses.
      - Description-only change (same role, new description): update PlannedMealCourse.description
        and regenerate only that course's recipe.
      - Changed role (remove + add): treat as remove then add in sequence.
      generate_recipe_for_course() is a focused path in recipe_service alongside the existing
      full-plan generation.
    status: done
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
    status: done
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

## Conventions

Cross-cutting rules this plan follows (see [_conventions.md](_conventions.md)):
[CONV-AUTH-OWNERSHIP](_conventions.md#conv-auth-ownership),
[CONV-SUMMARY-SCHEMA](_conventions.md#conv-summary-schema),
[CONV-DELETE-CASCADE](_conventions.md#conv-delete-cascade).

Task status is tracked in the `todos:` frontmatter above.

---

## Implementation notes

### Models involved
- `MealPlanWeek` — id, user_id, start_date, end_date, title; cascades to PlannedMeal + GroceryList
- `PlannedMeal` — id, meal_plan_week_id, day_index (0–6), meal_name, status (draft/planned)
- `PlannedMealCourse` — id, planned_meal_id, role (MealCourseRole), description (nullable str); one row per course slot; default is a single row with role=entree
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
Follows [CONV-SUMMARY-SCHEMA](_conventions.md#conv-summary-schema).

### Authorization
Follows [CONV-AUTH-OWNERSHIP](_conventions.md#conv-auth-ownership). PlannedMeal has no
`user_id`, so join up: e.g. for PATCH /meals/{meal_id}, verify
`planned_meal.meal_plan_week.user_id == current_user.id` and return 404 on mismatch.
