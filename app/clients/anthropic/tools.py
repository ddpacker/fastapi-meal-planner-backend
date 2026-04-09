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

_RECIPE_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "servings": {"type": "integer"},
        "instructions": {"type": "string"},
        "ingredients": {"type": "array", "items": _INGREDIENT_SCHEMA},
        "nutrition_estimate": {
            "type": "object",
            "properties": {
                "calories": {"type": "number"},
                "protein_g": {"type": "number"},
                "carbs_g": {"type": "number"},
                "fat_g": {"type": "number"},
                "per_serving": {"type": "boolean"},
            },
            "required": ["calories", "protein_g", "carbs_g", "fat_g", "per_serving"],
        },
    },
    "required": ["title", "servings", "instructions", "ingredients"],
}

GENERATE_RECIPES_TOOL = {
    "name": "submit_recipes",
    "description": "Submit the generated recipes as structured data.",
    "input_schema": {
        "type": "object",
        "properties": {
            "recipes": {"type": "array", "items": _RECIPE_SCHEMA},
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
                "anyOf": [_RECIPE_SCHEMA, {"type": "null"}],
                "description": "Revised recipe if structural changes were requested, otherwise null.",
            },
        },
        "required": ["assistant_message", "revised_recipe"],
    },
}
