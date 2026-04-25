from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel

from app.models.meal_plan import MealCourseRole


class RecipeIngredientBase(BaseModel):
    name: str
    quantity: Optional[float] = None
    unit: Optional[str] = None
    category: Optional[str] = None


class RecipeIngredientCreate(RecipeIngredientBase):
    pass


class RecipeIngredientRead(RecipeIngredientBase):
    id: int

    class Config:
        from_attributes = True


class RecipeBase(BaseModel):
    title: str
    instructions: str
    servings: Optional[int] = None


class RecipeCreate(RecipeBase):
    ingredients: List[RecipeIngredientCreate]
    role: Optional[MealCourseRole] = None


class RecipeRead(RecipeBase):
    id: int
    created_at: datetime
    updated_at: datetime
    ingredients: List[RecipeIngredientRead]

    class Config:
        from_attributes = True

