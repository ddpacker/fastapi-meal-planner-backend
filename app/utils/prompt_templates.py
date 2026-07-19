from app.models.meal_plan import MealCourseRole


def recipe_generation_prompt(
    meals: list[tuple[str, list[tuple[MealCourseRole, str | None]]]],
) -> str:
    lines: list[str] = []
    idx = 0
    for meal_name, courses in meals:
        for role, description in courses:
            idx += 1
            if description:
                lines.append(
                    f"{idx}. Meal \"{meal_name}\" — generate a {role.value} course. "
                    f"Specific guidance: {description}"
                )
            else:
                lines.append(
                    f"{idx}. Meal \"{meal_name}\" — generate a {role.value} course. "
                    "Use the meal name as your only theme hint; choose an appropriate dish freely."
                )
    slots_block = "\n".join(lines)
    n = idx
    roles = ", ".join(f"`{r.value}`" for r in MealCourseRole)
    return f"""You are a professional recipe creator. Generate one recipe for each numbered course slot below (in the same order).

Slots:
{slots_block}

Return exactly {n} recipe(s) in the same order as the slots above. You must call the tool submit_recipes with an object whose only payload field is a "recipes" array containing that many recipe objects.

Each recipe object must include a "role" field matching the slot ({roles}).

Ingredient output rules:
- Use singular ingredient names and singular unit names (for example: "carrot", "gram", "millilitre").
- Use metric units only (gram, kilogram, millilitre, litre, etc.). Never use imperial units (cup, tablespoon, teaspoon, ounce, pound, etc.).
- Convert ingredient quantities to metric values where needed."""


def chat_modify_prompt(recipe_json: str, history: list[dict], user_message: str) -> str:
    history_text = ""
    if history:
        lines = []
        for msg in history:
            role = msg.get("role", "user").capitalize()
            content = msg.get("content", "")
            lines.append(f"{role}: {content}")
        history_text = "\n".join(lines) + "\n"

    return f"""You are a helpful cooking assistant refining a recipe based on user feedback.

Current recipe:
{recipe_json}

Conversation so far:
{history_text}User: {user_message}

Reply conversationally. If the user requests structural changes to the recipe (ingredients, quantities, steps, or servings), provide a revised recipe. If no structural changes are needed, set revised_recipe to null."""
