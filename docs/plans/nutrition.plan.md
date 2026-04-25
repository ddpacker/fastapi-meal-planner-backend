---
name: nutrition
overview: >
  Per-recipe nutrition data via USDA FoodData Central. The NutritionInfo model and endpoints
  exist but POST /recipes/{recipe_id}/nutrition is a placeholder. This plan covers wiring
  nutrition_service to look up per-ingredient macros from USDA, aggregate them to per-serving
  totals, and persist the result. Unmatched ingredients leave those macro fields null.
todos:
  - id: nutrition-schema-and-endpoints
    content: >
      NutritionInfo model, NutritionInfoCreate/Read schemas, and both endpoints exist:
      POST /recipes/{recipe_id}/nutrition (placeholder — no real data),
      GET /recipes/{recipe_id}/nutrition (returns stored record).
      Endpoints require current_user; recipe ownership verified via Recipe.user_id.
    status: done

  - id: usda-client
    content: >
      Implement app/services/usda_client.py with:
        search_food(name: str) -> NutrientData | None
      Where NutrientData is a Pydantic model with per-100g fields:
        calories, protein_g, carbs_g, fat_g, fiber_g, sugar_g, sodium_mg
      Use httpx (already a dependency) to call USDA FoodData Central:
        GET https://api.nal.usda.gov/fdc/v1/foods/search?query={name}&api_key={key}
      Add USDA_API_KEY to app/config.py and environment variables (DEMO_KEY works for dev).
      Cache results in a FoodNutritionCache DB table (name, nutrient_data_json, fetched_at)
      to avoid redundant API calls across recipes. Cache hit: return stored row if fetched_at
      is within 30 days.
    status: pending

  - id: nutrition-service
    content: >
      Implement app/services/nutrition_service.py with:
        fetch_nutrition(recipe_id, db, user) -> NutritionInfo
      For each RecipeIngredient on the recipe: call usda_client.search_food(ingredient.name),
      scale returned per-100g values by (ingredient.quantity / 100), sum across all ingredients,
      divide by recipe.servings for per-serving totals.
      Ingredients with no USDA match contribute null to their macro fields (don't zero them out).
      Set NutritionInfo.source to "usda". Upsert: update existing row if one exists for recipe_id.
      Wire into POST /recipes/{recipe_id}/nutrition, replacing the placeholder insert.
    status: pending
    dependencies:
      - usda-client

  - id: nutrition-auto-generate
    content: >
      Optionally trigger nutrition fetch automatically after recipe generation
      (in recipe_service.generate_recipes_for_plan) so users don't need a separate API call.
      Make this opt-in via a query param: POST /meal-plans/{plan_id}/generate-recipes?include_nutrition=true.
      Default false to keep latency predictable (USDA adds one HTTP call per ingredient per recipe).
    status: pending
    dependencies:
      - nutrition-service

  - id: nutrition-tests
    content: >
      Tests for nutrition_service, usda_client, and endpoints:
      - usda_client: mock httpx responses via pytest-httpx or monkeypatch; assert cache hit skips HTTP call
      - POST /recipes/{recipe_id}/nutrition: calls nutrition_service, persists real macro data
      - GET /recipes/{recipe_id}/nutrition: returns stored record
      - Unmatched ingredient: assert that macro fields are null, not zero
      - 404 for recipe belonging to another user
      - Auto-generate via include_nutrition=true query param
    status: pending
    dependencies:
      - nutrition-service
      - nutrition-auto-generate
---

## Roadmap

| Status | Task |
|--------|------|
| ✅ Done | NutritionInfo model, schemas, and placeholder endpoints |
| ⏳ Pending | usda_client.py — USDA FoodData Central lookup with DB cache |
| ⏳ Pending | nutrition_service.py — aggregate per-ingredient macros, upsert NutritionInfo |
| ⏳ Pending | Optional auto-generation during recipe generation |
| ⏳ Pending | Tests (USDA mock, cache hit, null unmatched, router) |

---

## Implementation notes

### NutritionInfo model
Fields: calories, protein_g, carbs_g, fat_g, fiber_g, sugar_g, sodium_mg (all Numeric/Float, nullable),
per_serving (bool), source (str), one-to-one with Recipe via recipe_id unique constraint.
`per_serving=True` — values represent one serving; use Recipe.servings for total.

### USDA FoodData Central API
Base URL: https://api.nal.usda.gov/fdc/v1
Endpoint: GET /foods/search?query={ingredient_name}&api_key={USDA_API_KEY}
DEMO_KEY works for development (1000 req/hr per IP). Register for a free key for production
and add USDA_API_KEY to config.py and environment variables.
USDA returns nutrients per 100g — scale by (quantity_in_grams / 100).
Ingredient names should be singular (enforced by recipe generation prompt) for better match rate.

### FoodNutritionCache table
Columns: id, name (unique, indexed), nutrient_data_json, fetched_at.
Lookup key is ingredient name (lowercased). TTL: 30 days from fetched_at.
Alembic migration required.

### Null vs zero for unmatched ingredients
Use null, not 0, for macros that couldn't be resolved. Zero implies the ingredient has no
calories/protein/etc., which is misleading. The frontend should display null as "—" or "unknown".

### Source field values
- "usda" — aggregated from USDA FoodData Central per-ingredient lookups
- "manual" — user-provided (for a future manual entry endpoint)

### One-to-one upsert
NutritionInfo.recipe_id has a unique constraint. POST /recipes/{id}/nutrition should
upsert (update if exists, insert if not) rather than fail with 409 on a second call.
Use an explicit check-then-update pattern (select existing row, update fields, commit).
