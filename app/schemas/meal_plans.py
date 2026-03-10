from datetime import date, datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class PlannedMealBase(BaseModel):
    day_index: int = Field(ge=0, le=6)
    meal_name: str
    status: str = "draft"


class PlannedMealCreate(PlannedMealBase):
    pass


class PlannedMealRead(PlannedMealBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class MealPlanWeekBase(BaseModel):
    start_date: date
    end_date: date
    title: Optional[str] = None


class MealPlanWeekCreate(MealPlanWeekBase):
    planned_meals: List[PlannedMealCreate] = Field(default_factory=list)


class MealPlanWeekUpdate(BaseModel):
    title: Optional[str] = None
    planned_meals: Optional[List[PlannedMealCreate]] = None


class MealPlanWeekRead(MealPlanWeekBase):
    id: int
    created_at: datetime
    updated_at: datetime
    planned_meals: List[PlannedMealRead] = Field(default_factory=list)

    class Config:
        from_attributes = True

