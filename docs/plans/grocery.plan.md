---
name: grocery
overview: >
  Grocery list generation, management, and item tracking. grocery_service aggregates 
  RecipeIngredients from all recipes in a meal plan, collapsing by canonical ingredient 
  identity + unit per CONV-INGREDIENT-MODEL, and persists a GroceryList with GroceryItems. 
  Users can then check off items and adjust quantities as they shop.
todos:
  - id: grocery-generation
    content: >
      POST /grocery/meal-plans/{plan_id}/grocery-list is wired to 
      grocery_service.generate_grocery_list(). Service queries all RecipeIngredients 
      from recipes linked to the plan, aggregates by (name.lower(), unit), normalizes 
      category labels, and persists GroceryList + GroceryItems. Returns 201 with the list.
      Verified: does not create a second list if one already exists for the plan 
      (or overwrites — clarify behavior and enforce it consistently).
    status: done

  - id: grocery-item-management
    content: >
      GET /grocery/grocery-lists/{list_id} returns the full list with items.
      PATCH /grocery/grocery-items/{item_id} allows toggling checked and adjusting quantity.
      Both implemented. Verify user isolation: GroceryList → MealPlanWeek → user_id.
    status: done

  - id: grocery-idempotency
    content: >
      Define and enforce behavior when POST /grocery/meal-plans/{plan_id}/grocery-list 
      is called a second time (e.g., after recipes are regenerated). 
      Atomically delete existing GroceryList + items, then regenerate.
      This keeps the endpoint idempotent with fresh data after recipe updates.
      Add a test that calls the endpoint twice and verifies no duplicate items.
    status: pending
    dependencies:
      - grocery-generation

  - id: grocery-item-add-remove
    content: >
      Allow users to manually add or remove items from a grocery list after generation:
      POST /grocery/grocery-lists/{list_id}/items (add a custom item),
      DELETE /grocery/grocery-items/{item_id} (remove an item).
      Use GroceryItemCreate schema (name, quantity, unit, category) for POST.
      Return 201 with GroceryItemRead for POST; 204 for DELETE.
      Verify list ownership via GroceryList → MealPlanWeek → user_id for both.
    status: pending
    dependencies:
      - grocery-item-management

  - id: grocery-list-export
    content: >
      Add GET /grocery/grocery-lists/{list_id}/export?format=text that returns a 
      plain-text or markdown representation of the grocery list grouped by category.
      No new model needed — derive from existing GroceryItem rows.
      Return as text/plain with Content-Disposition: attachment.
      This gives users something they can copy into a notes app or share.
    status: pending
    dependencies:
      - grocery-item-management

  - id: grocery-tests
    content: >
      Existing tests in test_grocery.py and test_grocery_service.py cover generation, 
      get, and patch. Add tests for:
      - Idempotent regeneration (double-call, no duplicates)
      - POST + DELETE individual items
      - Export endpoint (response content-type, grouping by category)
      - Cross-user 404 for all grocery endpoints
    status: pending
    dependencies:
      - grocery-idempotency
      - grocery-item-add-remove
      - grocery-list-export
---

## Conventions

Cross-cutting rules this plan follows (see [_conventions.md](_conventions.md)):
[CONV-AUTH-OWNERSHIP](_conventions.md#conv-auth-ownership),
[CONV-CATEGORY-ENUM](_conventions.md#conv-category-enum),
[CONV-DELETE-CASCADE](_conventions.md#conv-delete-cascade),
[CONV-INGREDIENT-MODEL](_conventions.md#conv-ingredient-model).

Task status is tracked in the `todos:` frontmatter above.

---

## Implementation notes

### Models involved
- `GroceryList` — id, meal_plan_week_id, title, notes, timestamps
- `GroceryItem` — id, grocery_list_id, name, total_quantity (Numeric), unit, category, checked.
  _Target per [CONV-INGREDIENT-MODEL](_conventions.md#conv-ingredient-model):_ carry
  `ingredient_id` (catalog FK) instead of free-text `name`; lands with the catalog join below.

### Aggregation logic (in grocery_service)
Category and name come from the joined catalog row (`RecipeIngredient.ingredient`), not from
`RecipeIngredient` — the name/category columns moved to `Ingredient` in #28. Sum `quantity`
(Numeric) per group. _Target per [CONV-INGREDIENT-MODEL](_conventions.md#conv-ingredient-model):_
key the aggregation on `(ingredient_id, unit)` rather than `(ingredient.name, unit)`, so
collapsed identities sum cleanly regardless of surface name.

### Category normalization
Category is a property of the catalog `Ingredient` row (per
[CONV-INGREDIENT-MODEL](_conventions.md#conv-ingredient-model)), normalized to the canonical
set in [CONV-CATEGORY-ENUM](_conventions.md#conv-category-enum) at the service level so export
grouping stays consistent.

### Authorization for nested resources
Follows [CONV-AUTH-OWNERSHIP](_conventions.md#conv-auth-ownership). GroceryItem stores no
`user_id`, so join up: GroceryItem → GroceryList → MealPlanWeek → `user_id`. Return 404 on
mismatch.

### Idempotent regeneration transaction
Use a single DB transaction: delete existing GroceryList (cascade removes items), 
then insert new GroceryList + items, commit once. If anything fails, nothing is persisted.
