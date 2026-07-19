from collections import defaultdict
from typing import Dict, Tuple

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.grocery import GroceryItem, GroceryList
from app.models.meal_plan import MealPlanWeek, PlannedMealRecipe
from app.models.recipe import RecipeIngredient
from app.models.user import User


def generate_grocery_list(plan_id: int, db: Session, user: User) -> GroceryList:
    plan = db.execute(
        select(MealPlanWeek)
        .where(MealPlanWeek.id == plan_id, MealPlanWeek.user_id == user.id)
        .options(selectinload(MealPlanWeek.planned_meals))
    ).scalar_one_or_none()
    if plan is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Meal plan not found")

    meal_ids = [meal.id for meal in plan.planned_meals]

    recipe_links = db.execute(
        select(PlannedMealRecipe).where(PlannedMealRecipe.planned_meal_id.in_(meal_ids))
    ).scalars().all()
    recipe_ids = [link.recipe_id for link in recipe_links]

    if not recipe_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No recipes found for this meal plan",
        )

    ingredients = db.execute(
        select(RecipeIngredient)
        .where(RecipeIngredient.recipe_id.in_(recipe_ids))
        .options(selectinload(RecipeIngredient.ingredient))
    ).scalars().all()

    if not ingredients:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No ingredients found in recipes for this meal plan",
        )

    aggregated: Dict[Tuple[str, str | None], Tuple[float, str | None]] = defaultdict(
        lambda: (0.0, None)
    )

    for ingr in ingredients:
        key = (ingr.ingredient.name, ingr.unit)
        current_qty, current_cat = aggregated[key]
        line_qty = float(ingr.quantity) if ingr.quantity is not None else 0.0
        new_qty = current_qty + line_qty
        category = current_cat or ingr.ingredient.category
        aggregated[key] = (new_qty, category)

    grocery_list = GroceryList(
        meal_plan_week_id=plan.id,
        title=f"Grocery List for {plan.title or f'Week of {plan.start_date}'}",
    )
    db.add(grocery_list)
    db.flush()

    for (name, unit), (total_qty, category) in aggregated.items():
        db.add(
            GroceryItem(
                grocery_list_id=grocery_list.id,
                name=name,
                total_quantity=total_qty if total_qty > 0 else None,
                unit=unit,
                category=category,
                checked=False,
            )
        )

    db.commit()

    return db.execute(
        select(GroceryList)
        .where(GroceryList.id == grocery_list.id)
        .options(selectinload(GroceryList.items))
    ).scalar_one()
