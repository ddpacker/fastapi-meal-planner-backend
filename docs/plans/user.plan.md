---
name: user
overview: >
  User account management beyond authentication. Covers profile endpoints (read, update,
  delete), user preferences (unit system for display), and account deletion with cascade.
  Auth (register, login, logout, Google OIDC) lives in auth.plan.md.
todos:
  - id: user-profile-endpoints
    content: >
      Add GET /users/me and PATCH /users/me.
      GET returns the current user as UserRead (id, email, created_at — no password_hash).
      PATCH accepts UserUpdate schema with optional fields: email, password (requires
      current_password for verification before accepting a new one).
      Email change must check uniqueness before updating.
      Return updated UserRead on success.
    status: completed

  - id: user-preferences
    content: >
      Add a UserPreferences model (or a preferences JSONB column on User) to store
      user settings. First preference: unit_system (metric | imperial, default metric).
      The backend always stores and returns ingredient quantities in metric units
      (grams, ml, etc.) — the AI is instructed to output metric via the generation prompt.
      unit_system is a display hint for the frontend to apply conversions; no backend
      conversion logic needed.
      Add GET /users/me/preferences and PATCH /users/me/preferences.
      Include unit_system in UserRead or as a nested PreferencesRead.
    status: pending
    dependencies:
      - user-profile-endpoints

  - id: user-delete
    content: >
      Add DELETE /users/me. Requires the user to confirm their password in the request body
      to prevent accidental deletion.
      Cascade: deleting a User must remove all owned MealPlanWeek, Recipe, ChatSession,
      GroceryList, and NutritionInfo rows. Verify SQLAlchemy cascade config covers all
      relationships. RevokedToken rows for the user's tokens can remain (they expire naturally).
      Return 204. Add a test that confirms all related rows are removed.
    status: pending
    dependencies:
      - user-profile-endpoints

  - id: user-tests
    content: >
      Tests for all user endpoints:
      - GET /users/me returns correct UserRead
      - PATCH /users/me: email change (success + duplicate 400), password change
        (wrong current_password 400, success)
      - GET + PATCH /users/me/preferences: unit_system persists
      - DELETE /users/me: wrong password 400, success + cascade verification
      - All endpoints return 401 without a valid token
    status: pending
    dependencies:
      - user-preferences
      - user-delete
---

## Roadmap

| Status | Task |
|--------|------|
| ✅ Done | GET /users/me + PATCH /users/me (email, password change) |
| ⏳ Pending | User preferences (unit_system: metric/imperial) |
| ⏳ Pending | DELETE /users/me with cascade verification |
| ⏳ Pending | Tests |

---

## Implementation notes

### UserUpdate schema
All fields optional: email (validate format + uniqueness), password (requires current_password).
Never accept password_hash directly. Validate current_password via verify_password() before
allowing a password change.

### Unit system convention
The AI generation prompt (recipe_generation_prompt) must instruct the model to return all
quantities in metric units (grams, ml, litre, etc.). unit_system stored in UserPreferences
is purely a frontend display hint — the API always returns metric values. This also ensures
USDA nutrition lookups (which expect per-100g) work without unit conversion.

### UserPreferences storage
A separate UserPreferences table (one-to-one with User via user_id) is cleaner than a JSONB
column if preferences grow. Start with the table; add an Alembic migration.
Fields: id, user_id (unique FK), unit_system (enum: metric/imperial, default metric).

### Cascade on DELETE /users/me
SQLAlchemy cascade="all, delete-orphan" should already cover MealPlanWeek → PlannedMeal →
PlannedMealRecipe and Recipe → RecipeIngredient → NutritionInfo chains via User relationships.
Verify each relationship on the User model before relying on it. Return 404 if user is
somehow not found (shouldn't happen with a valid token, but be defensive).
