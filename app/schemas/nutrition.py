from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict


class RecipeNutritionBase(BaseModel):
    calories: Optional[float] = None
    protein_g: Optional[float] = None
    carbs_g: Optional[float] = None
    fat_g: Optional[float] = None
    fiber_g: Optional[float] = None
    sugar_g: Optional[float] = None
    sodium_mg: Optional[float] = None
    micro_nutrients_json: Optional[list[dict[str, Any]]] = None
    per_serving: bool = True
    source: Optional[str] = None


class RecipeNutritionRead(RecipeNutritionBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    recipe_id: int
    created_at: datetime
    updated_at: datetime
