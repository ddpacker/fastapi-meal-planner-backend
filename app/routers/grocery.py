from collections import defaultdict
from typing import Dict, Tuple

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.db.session import get_db
from app.models.grocery import GroceryItem, GroceryList
from app.models.meal_plan import MealPlanWeek, PlannedMeal, PlannedMealRecipe
from app.models.recipe import RecipeIngredient
from app.models.user import User
from app.schemas.grocery import GroceryItemUpdate, GroceryListRead


router = APIRouter(prefix="/grocery", tags=["grocery"])


@router.post("/meal-plans/{plan_id}/grocery-list", response_model=GroceryListRead, status_code=status.HTTP_201_CREATED)
def generate_grocery_list(
    plan_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> GroceryList:
    """Generate a grocery list from all recipes in a meal plan."""
    plan = (
        db.query(MealPlanWeek)
        .filter(MealPlanWeek.id == plan_id, MealPlanWeek.user_id == current_user.id)
        .first()
    )
    if not plan:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Meal plan not found")

    # Get all recipe IDs linked to meals in this plan
    meal_ids = [meal.id for meal in plan.planned_meals]
    recipe_links = (
        db.query(PlannedMealRecipe)
        .filter(PlannedMealRecipe.planned_meal_id.in_(meal_ids))
        .all()
    )
    recipe_ids = [link.recipe_id for link in recipe_links]

    if not recipe_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No recipes found for this meal plan",
        )

    # Get all ingredients for these recipes
    ingredients = (
        db.query(RecipeIngredient)
        .filter(RecipeIngredient.recipe_id.in_(recipe_ids))
        .all()
    )

    if not ingredients:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No ingredients found in recipes for this meal plan",
        )

    # Aggregate ingredients by (name, unit) and sum quantities
    # Key: (name_lower, unit or None) -> (total_quantity, category)
    aggregated: Dict[Tuple[str, str | None], Tuple[float, str | None]] = defaultdict(
        lambda: (0.0, None)
    )

    for ingr in ingredients:
        key = (ingr.name.lower().strip(), ingr.unit)
        current_qty, current_cat = aggregated[key]
        new_qty = current_qty + (ingr.quantity or 0.0)
        # Use first non-None category encountered
        category = current_cat or ingr.category
        aggregated[key] = (new_qty, category)

    # Create grocery list
    grocery_list = GroceryList(
        meal_plan_week_id=plan.id,
        title=f"Grocery List for {plan.title or f'Week of {plan.start_date}'}",
    )
    db.add(grocery_list)
    db.flush()

    # Create grocery items from aggregated ingredients
    for (name_lower, unit), (total_qty, category) in aggregated.items():
        # Use original casing from first ingredient if available, otherwise use normalized name
        original_name = next(
            (ingr.name for ingr in ingredients if ingr.name.lower().strip() == name_lower),
            name_lower.title(),
        )

        item = GroceryItem(
            grocery_list_id=grocery_list.id,
            name=original_name,
            total_quantity=total_qty if total_qty > 0 else None,
            unit=unit,
            category=category,
            checked=False,
        )
        db.add(item)

    db.commit()
    db.refresh(grocery_list)
    return grocery_list


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
