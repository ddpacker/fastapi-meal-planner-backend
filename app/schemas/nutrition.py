from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class NutritionInfoBase(BaseModel):
    calories: Optional[float] = None
    protein_g: Optional[float] = None
    carbs_g: Optional[float] = None
    fat_g: Optional[float] = None
    fiber_g: Optional[float] = None
    sugar_g: Optional[float] = None
    sodium_mg: Optional[float] = None
    per_serving: bool = True
    source: Optional[str] = None


class NutritionInfoCreate(NutritionInfoBase):
    pass


class NutritionInfoRead(NutritionInfoBase):
    id: int
    recipe_id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
