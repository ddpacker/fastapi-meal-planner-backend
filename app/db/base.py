"""
Import all SQLAlchemy models here so Alembic can discover them via Base.metadata.
"""

from app.db.base_class import Base
from app.models.user import User
from app.models.meal_plan import MealPlanWeek, PlannedMeal, PlannedMealRecipe
from app.models.recipe import Recipe, RecipeIngredient
from app.models.grocery import GroceryList, GroceryItem
from app.models.chat import ChatSession, ChatMessage
from app.models.nutrition import NutritionInfo

__all__ = [
    "Base",
    "User",
    "MealPlanWeek",
    "PlannedMeal",
    "Recipe",
    "RecipeIngredient",
    "GroceryList",
    "GroceryItem",
    "ChatSession",
    "ChatMessage",
    "NutritionInfo",
    "PlannedMealRecipe",
]

