def recipe_generation_prompt(meal_names: list[str]) -> str:
    names_list = "\n".join(f"- {name}" for name in meal_names)
    return f"""You are a professional recipe creator. Generate one recipe for each of the following meals:

{names_list}

Return exactly {len(meal_names)} recipe(s) in the same order as the input list. You must call the tool submit_recipes with an object whose only payload field is a "recipes" array containing that many recipe objects."""


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

Reply conversationally. If the user requests structural changes to the recipe (ingredients, quantities, instructions, or servings), provide a revised recipe. If no structural changes are needed, set revised_recipe to null."""
