from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict

from app.models.meal_plan import MealCourseRole


class RecipeIngredientBase(BaseModel):
    name: str
    quantity: Optional[float] = None
    unit: Optional[str] = None
    category: Optional[str] = None


class RecipeIngredientCreate(RecipeIngredientBase):
    pass


class RecipeIngredientRead(RecipeIngredientBase):
    model_config = ConfigDict(from_attributes=True)

    id: int


class RecipeStepBase(BaseModel):
    step_number: int
    text: str


class RecipeStepCreate(RecipeStepBase):
    pass


class RecipeStepRead(RecipeStepBase):
    model_config = ConfigDict(from_attributes=True)

    id: int


class RecipeBase(BaseModel):
    title: str
    servings: Optional[int] = None


class RecipeCreate(RecipeBase):
    steps: List[RecipeStepCreate]
    ingredients: List[RecipeIngredientCreate]
    role: Optional[MealCourseRole] = None


class RecipeRead(RecipeBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime
    steps: List[RecipeStepRead]
    ingredients: List[RecipeIngredientRead]
