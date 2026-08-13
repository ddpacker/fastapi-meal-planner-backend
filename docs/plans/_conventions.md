# Plan Conventions

Single source of truth for cross-cutting decisions that apply across every domain plan.
Each convention has a stable ID. Plans reference conventions by ID (e.g. "auth per
[CONV-AUTH-OWNERSHIP](#conv-auth-ownership)") instead of restating them, so changing an
approach is a one-file edit here rather than an edit in every plan.

When you change your mind about one of these, edit it **here** and the change propagates to
every plan that references it. If a plan genuinely needs to deviate, it should say so
explicitly and note *why* — an unexplained divergence is a bug.

> Status of individual tasks lives in each plan's `todos:` frontmatter — that is the single
> source of truth for progress. Plans no longer carry a Roadmap table mirroring it.

---

## CONV-AUTH-OWNERSHIP

All data is scoped to the authenticated user. Every endpoint requires `current_user` and
every query filters by ownership.

- Filter directly by `user_id == current_user.id` when the row carries `user_id`
  (e.g. `Recipe`, `MealPlanWeek`, `ChatSession`).
- For nested resources that don't store `user_id`, verify ownership by joining up to the
  owning row's `user_id`:
  - `PlannedMeal` / `PlannedMealCourse` → `MealPlanWeek.user_id`
  - `GroceryItem` → `GroceryList` → `MealPlanWeek.user_id`
  - `NutritionInfo` → `Recipe.user_id`
- Return **404 (not 403)** when a row exists but belongs to another user — never leak
  existence.
- Prefer the direct `user_id` column when a row already carries one (e.g. `ChatSession` has
  both `recipe_id` and `user_id`; check `user_id` directly rather than joining through
  `Recipe`).

## CONV-PAGINATION

Two paging styles, by resource kind:

- **Library / collection listings** (recipes, chat-session lists): `page` + `page_size`
  query params, `page_size` default **20**.
- **Message / activity history** (chat messages within a session): `offset` + `limit`
  query params, `limit` default **50**.

Ordering is defined per endpoint (e.g. messages always `created_at asc`; plan lists
`start_date desc`).

## CONV-SUMMARY-SCHEMA

List endpoints return a lightweight `XxxSummaryRead` schema that **omits nested children**
(ingredients, steps, messages) for payload size and query cost. Full detail — including
nested collections — is served only by the single-resource `GET /{id}` endpoint.

Examples: `RecipeSummaryRead` (id, title, servings, source_model, created_at),
`ChatSessionSummaryRead` (id, title, created_at, message_count),
`MealPlanWeekSummaryRead` (adds meal_count, has_grocery_list). Derived counts are computed in
the router (subquery or `len()` on eager-loaded relationships), never stored as columns.

## CONV-METRIC-SINGULAR

The AI generation and chat-modify prompts instruct the model to return, and the backend
always stores and returns:

- Ingredient **names and unit names in singular form** ("carrot" not "carrots", "cup" not
  "cups") for clean USDA lookups.
- All **quantities in metric units** (gram, ml, litre, …) — never imperial.

`UserPreferences.unit_system` (metric | imperial, default metric) is a **frontend display
hint only** — the API always returns metric; the client converts for display. Keeping storage
metric also lets USDA nutrition lookups (per-100g) work without unit conversion. Any change to
`sample_recipes.json` must keep the FakeClient output consistent with these conventions.

## CONV-CATEGORY-ENUM

Ingredient / grocery categories draw from a single canonical set enforced at the service
layer: `produce | dairy | meat | pantry | frozen | other`. Fall back to `other` when the AI
returns a missing or unrecognized category. This keeps grocery export grouping consistent.

## CONV-INGREDIENT-MODEL

`Ingredient` rows are **canonical food identities**, deduplicated to their base form.
Preparation and state belong to the *recipe association*, never to the ingredient.

- **Identity = the base food.** `jasmine rice` — never `cooked jasmine rice`, `day-old
  jasmine rice`, or `jasmine rice, diced`. The `name` is unique, lowercase and singular per
  [CONV-METRIC-SINGULAR](#conv-metric-singular); `category` is drawn from
  [CONV-CATEGORY-ENUM](#conv-category-enum).
- **Preparation/state is an attribute of `RecipeIngredient`** — an optional free-text
  `preparation` field ("cooked", "day-old", "finely diced"). Two recipe lines that differ
  only in preparation reference the **same** `Ingredient` row.
- **Collapse on write.** Before creating an `Ingredient`, the service normalizes the AI/user
  name to its canonical base (strip preparation/state words, singularize) and reuses an
  existing row when one matches. The AI is *prompted* to emit base names but is not *trusted*
  to — the service owns the collapse.
- **Grocery aggregation keys on `ingredient_id` + `unit`**, so lines that collapsed to one
  identity sum into a single `GroceryItem`. `GroceryItem` joins the catalog by
  `ingredient_id` rather than storing a free-text name.
- **Ownership of detail:** this convention owns the *identity / preparation-split rule*;
  [ARCHITECTURE.md §3](../ARCHITECTURE.md) owns the concrete *field list*. Change the rule
  here, the schema there.

## CONV-DELETE-CASCADE

Destructive endpoints follow a shared shape:

- Return **204** on success.
- Rely on DB / SQLAlchemy `cascade="all, delete-orphan"` for related rows rather than
  manual per-row deletes; verify the cascade config on the owning model before relying on it.
- Every delete endpoint ships a test that asserts the related rows are actually removed
  (assert DB state, not just the response code).

## CONV-AI-CLIENT-INJECTION

Anything that talks to the AI provider goes through the abstract client, never a vendor SDK
directly.

- Services depend only on `AIClientBase` (`app/clients/base.py`) — never import a concrete
  provider.
- Routers inject the client via `get_ai_client` (`app/clients/factory.py`), selected by the
  `AI_PROVIDER` setting (`anthropic` | `test`).
- All prompt strings live in `app/utils/prompt_templates.py` — nowhere else.
- Log AI request **metadata only** (provider, model name, token usage) at INFO — never log
  prompt or response content.
- Tests run with `AI_PROVIDER=test`, assert on `FakeClient.recorded_calls`, and never set
  `ANTHROPIC_API_KEY`.

---

## Related references

- Canonical data model and endpoint catalogue: [ARCHITECTURE.md](../ARCHITECTURE.md).
- Per-domain task lists and deltas: the `*.plan.md` files in this directory.

---

## Changelog

One line per decision change: date, what changed, and **why**. Git records the *what/when* of
every file; this log records the *why* git can't. When you change a `CONV-*`, add a line here.

- **2026-08-13** — Added `CONV-INGREDIENT-MODEL`. *Why:* ingredient rows were drifting toward
  preparation-specific identities ("cooked jasmine rice" vs "jasmine rice"), which fragments
  grocery aggregation and USDA lookups. Preparation now lives on `RecipeIngredient`; identity
  collapses to the base food. Supersedes the ad-hoc ingredient notes across the recipe,
  nutrition, and grocery plans.
- **2026-08-13** — Extracted cross-cutting decisions into this file with stable `CONV-*` IDs;
  domain plans now reference by ID instead of restating. *Why:* one edit propagates instead of
  N drifting copies.
