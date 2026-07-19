"""Anthropic tool definitions used for structured outputs."""

_INGREDIENT_SCHEMA = {
    "type": "object",
    "properties": {
        "name": {"type": "string"},
        "quantity": {"type": ["number", "null"]},
        "unit": {"type": ["string", "null"]},
        "category": {"type": ["string", "null"]},
    },
    "required": ["name", "quantity", "unit", "category"],
}

_STEP_SCHEMA = {
    "type": "object",
    "properties": {
        "step_number": {"type": "integer"},
        "text": {"type": "string"},
    },
    "required": ["step_number", "text"],
}

_RECIPE_SCHEMA_CHAT = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "servings": {"type": "integer"},
        "steps": {"type": "array", "items": _STEP_SCHEMA},
        "ingredients": {"type": "array", "items": _INGREDIENT_SCHEMA},
    },
    "required": ["title", "servings", "steps", "ingredients"],
}

_RECIPE_SCHEMA_GENERATION = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "role": {
            "type": "string",
            "enum": ["starter", "entree", "side", "dessert"],
            "description": "Course role for this slot; must match the requested slot.",
        },
        "servings": {"type": "integer"},
        "steps": {"type": "array", "items": _STEP_SCHEMA},
        "ingredients": {"type": "array", "items": _INGREDIENT_SCHEMA},
    },
    "required": ["title", "role", "servings", "steps", "ingredients"],
}

GENERATE_RECIPES_TOOL = {
    "name": "submit_recipes",
    "description": "Submit the generated recipes. The tool input must be a single object with a property named 'recipes' (array of recipe objects), one per meal+course slot, in the same order as the prompt (flattened across meals).",
    "input_schema": {
        "type": "object",
        "properties": {
            "recipes": {"type": "array", "items": _RECIPE_SCHEMA_GENERATION},
        },
        "required": ["recipes"],
    },
}

CHAT_MODIFY_TOOL = {
    "name": "submit_response",
    "description": "Submit a conversational reply and an optional revised recipe.",
    "input_schema": {
        "type": "object",
        "properties": {
            "assistant_message": {"type": "string"},
            "revised_recipe": {
                "anyOf": [_RECIPE_SCHEMA_CHAT, {"type": "null"}],
                "description": "Revised recipe if structural changes were requested, otherwise null.",
            },
        },
        "required": ["assistant_message", "revised_recipe"],
    },
}
