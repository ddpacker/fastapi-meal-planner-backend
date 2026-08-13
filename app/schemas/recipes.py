from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict

from app.models.meal_plan import MealCourseRole


class IngredientBase(BaseModel):
    name: str
    category: Optional[str] = None


class IngredientCreate(IngredientBase):
    pass


class IngredientRead(IngredientBase):
    model_config = ConfigDict(from_attributes=True)

    id: int


class RecipeIngredientCreate(BaseModel):
    name: str
    quantity: Optional[float] = None
    unit: Optional[str] = None
    category: Optional[str] = None
    preparation: Optional[str] = None


class RecipeIngredientRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    quantity: Optional[float] = None
    unit: Optional[str] = None
    preparation: Optional[str] = None
    ingredient: IngredientRead


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


class RecipeUpdate(RecipeBase):
    steps: List[RecipeStepCreate]
    ingredients: List[RecipeIngredientCreate]


class RecipeSummaryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    servings: Optional[int] = None
    source_model: Optional[str] = None
    created_at: datetime
