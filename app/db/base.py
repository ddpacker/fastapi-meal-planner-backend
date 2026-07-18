"""
Import all SQLAlchemy models here so Alembic can discover them via Base.metadata.
"""

from app.db.base_class import Base
from app.models.user import User
from app.models.user_preferences import UserPreferences
from app.models.revoked_token import RevokedToken
from app.models.meal_plan import MealPlanWeek, PlannedMeal, PlannedMealCourse, PlannedMealRecipe
from app.models.ingredient import Ingredient
from app.models.recipe import Recipe, RecipeIngredient, RecipeStep
from app.models.grocery import GroceryList, GroceryItem
from app.models.chat import ChatSession, ChatMessage
from app.models.nutrition import NutritionInfo

__all__ = [
    "Base",
    "User",
    "UserPreferences",
    "RevokedToken",
    "MealPlanWeek",
    "PlannedMeal",
    "PlannedMealCourse",
    "Ingredient",
    "Recipe",
    "RecipeStep",
    "RecipeIngredient",
    "GroceryList",
    "GroceryItem",
    "ChatSession",
    "ChatMessage",
    "NutritionInfo",
    "PlannedMealRecipe",
]

