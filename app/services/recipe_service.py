"""Recipe generation for meal plans via the AI client."""

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from fastapi import HTTPException, status

from app.clients.base import AIClientBase
from app.config import get_settings
from app.models.meal_plan import MealPlanWeek, PlannedMeal, PlannedMealRecipe
from app.models.recipe import Recipe, RecipeIngredient
from app.models.user import User


def generate_recipes_for_plan(
    plan_id: int,
    db: Session,
    ai_client: AIClientBase,
    user: User,
) -> MealPlanWeek:
    """Generate recipes for each planned meal, persist rows, and return the updated week."""
    plan = db.execute(
        select(MealPlanWeek)
        .where(MealPlanWeek.id == plan_id, MealPlanWeek.user_id == user.id)
        .options(selectinload(MealPlanWeek.planned_meals))
    ).scalar_one_or_none()
    if plan is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Meal plan not found")

    meals = sorted(plan.planned_meals, key=lambda m: (m.day_index, m.id))
    meal_names = [m.meal_name for m in meals]
    if not meal_names:
        return plan

    _remove_existing_meal_recipe_links(db, meals)
    db.flush()

    generated = ai_client.generate_recipes(meal_names)
    if len(generated) != len(meal_names):
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="AI returned a different number of recipes than planned meals",
        )

    provider_label = get_settings().ai_provider.value

    for meal, recipe_create in zip(meals, generated, strict=True):
        recipe = Recipe(
            user_id=user.id,
            title=recipe_create.title,
            instructions=recipe_create.instructions,
            servings=recipe_create.servings,
            source_model=provider_label,
        )
        db.add(recipe)
        db.flush()

        for ing in recipe_create.ingredients:
            db.add(
                RecipeIngredient(
                    recipe_id=recipe.id,
                    name=ing.name,
                    quantity=ing.quantity,
                    unit=ing.unit,
                    category=ing.category,
                )
            )

        db.add(
            PlannedMealRecipe(
                planned_meal_id=meal.id,
                recipe_id=recipe.id,
                role="entree",
            )
        )
        meal.status = "planned"

    db.commit()

    return db.execute(
        select(MealPlanWeek)
        .where(MealPlanWeek.id == plan_id)
        .options(selectinload(MealPlanWeek.planned_meals))
    ).scalar_one()


def _remove_existing_meal_recipe_links(db: Session, meals: list[PlannedMeal]) -> None:
    """Drop planned-meal→recipe links for these slots and delete recipes that are no longer used."""
    planned_meal_ids = [m.id for m in meals]
    links = db.execute(
        select(PlannedMealRecipe).where(PlannedMealRecipe.planned_meal_id.in_(planned_meal_ids))
    ).scalars().all()
    recipe_ids = {link.recipe_id for link in links}
    for link in links:
        db.delete(link)

    for rid in recipe_ids:
        remaining = db.execute(
            select(func.count())
            .select_from(PlannedMealRecipe)
            .where(PlannedMealRecipe.recipe_id == rid)
        ).scalar_one()
        if remaining == 0:
            recipe = db.get(Recipe, rid)
            if recipe is not None:
                db.delete(recipe)
