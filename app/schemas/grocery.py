from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel


class GroceryItemBase(BaseModel):
    name: str
    total_quantity: Optional[float] = None
    unit: Optional[str] = None
    category: Optional[str] = None
    checked: bool = False


class GroceryItemCreate(GroceryItemBase):
    pass


class GroceryItemUpdate(BaseModel):
    total_quantity: Optional[float] = None
    checked: Optional[bool] = None


class GroceryItemRead(GroceryItemBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class GroceryListBase(BaseModel):
    title: Optional[str] = None
    notes: Optional[str] = None


class GroceryListCreate(GroceryListBase):
    pass


class GroceryListRead(GroceryListBase):
    id: int
    meal_plan_week_id: int
    created_at: datetime
    updated_at: datetime
    items: List[GroceryItemRead] = []

    class Config:
        from_attributes = True
