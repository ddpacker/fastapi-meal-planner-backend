from datetime import date, datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.models.meal_plan import MealCourseRole


class PlannedMealCourseCreate(BaseModel):
    role: MealCourseRole
    description: Optional[str] = None


class PlannedMealCourseRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    role: MealCourseRole
    description: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class PlannedMealRecipeRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    planned_meal_id: int
    planned_meal_course_id: int
    recipe_id: int
    role: MealCourseRole


class PlannedMealBase(BaseModel):
    day_index: int = Field(ge=0, le=6)
    meal_name: str
    status: str = "draft"


class PlannedMealCreate(PlannedMealBase):
    courses: Optional[List[PlannedMealCourseCreate]] = None


class PlannedMealRead(PlannedMealBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime
    courses: List[PlannedMealCourseRead]


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
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime
    planned_meals: List[PlannedMealRead] = Field(default_factory=list)
