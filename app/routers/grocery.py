from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.db.session import get_db
from app.models.grocery import GroceryItem, GroceryList
from app.models.meal_plan import MealPlanWeek
from app.models.user import User
from app.schemas.grocery import GroceryItemUpdate, GroceryListRead
from app.services import grocery_service


router = APIRouter(prefix="/grocery", tags=["grocery"])


@router.post("/meal-plans/{plan_id}/grocery-list", response_model=GroceryListRead, status_code=status.HTTP_201_CREATED)
def generate_grocery_list(
    plan_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> GroceryList:
    return grocery_service.generate_grocery_list(plan_id, db, current_user)


@router.get("/grocery-lists/{list_id}", response_model=GroceryListRead)
def get_grocery_list(
    list_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> GroceryList:
    """Get a grocery list with all items."""
    grocery_list = (
        db.query(GroceryList)
        .join(MealPlanWeek)
        .filter(
            GroceryList.id == list_id,
            MealPlanWeek.user_id == current_user.id,
        )
        .first()
    )
    if not grocery_list:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Grocery list not found")
    return grocery_list


@router.patch("/grocery-items/{item_id}", response_model=GroceryListRead)
def update_grocery_item(
    item_id: int,
    item_update: GroceryItemUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> GroceryList:
    """Update a grocery item (toggle checked status or adjust quantity)."""
    item = (
        db.query(GroceryItem)
        .join(GroceryList)
        .join(MealPlanWeek)
        .filter(
            GroceryItem.id == item_id,
            MealPlanWeek.user_id == current_user.id,
        )
        .first()
    )
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Grocery item not found")

    if item_update.total_quantity is not None:
        item.total_quantity = item_update.total_quantity
    if item_update.checked is not None:
        item.checked = item_update.checked

    db.commit()
    db.refresh(item.grocery_list)
    return item.grocery_list
