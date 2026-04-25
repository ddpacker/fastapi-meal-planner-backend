"""Recipe generation for meal plans via the AI client."""

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from fastapi import HTTPException, status

from app.clients.base import AIClientBase, MealGenerationMeal
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
        .options(
            selectinload(MealPlanWeek.planned_meals).selectinload(PlannedMeal.courses),
        )
    ).scalar_one_or_none()
    if plan is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Meal plan not found")

    meals = sorted(plan.planned_meals, key=lambda m: (m.day_index, m.id))
    if not meals:
        return plan

    for meal in meals:
        if not meal.courses:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Planned meal has no courses",
            )

    meal_inputs: list[MealGenerationMeal] = _meal_generation_inputs(meals)
    slot_count = sum(len(courses) for _, courses in meal_inputs)

    _remove_existing_meal_recipe_links(db, meals)
    db.flush()

    generated = ai_client.generate_recipes(meal_inputs)
    if len(generated) != slot_count:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="AI returned a different number of recipes than course slots",
        )

    provider_label = get_settings().ai_provider.value

    gen_iter = iter(generated)
    for meal in meals:
        for course in sorted(meal.courses, key=lambda c: c.id):
            recipe_create = next(gen_iter)
            if recipe_create.role is not None and recipe_create.role != course.role:
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail="AI returned a recipe whose role does not match the course slot",
                )

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
                    planned_meal_course_id=course.id,
                    recipe_id=recipe.id,
                    role=course.role,
                )
            )
            meal.status = "planned"

    db.commit()

    return db.execute(
        select(MealPlanWeek)
        .where(MealPlanWeek.id == plan_id)
        .options(
            selectinload(MealPlanWeek.planned_meals).selectinload(PlannedMeal.courses),
        )
    ).scalar_one()


def _meal_generation_inputs(meals: list[PlannedMeal]) -> list[MealGenerationMeal]:
    out: list[MealGenerationMeal] = []
    for m in meals:
        ordered = sorted(m.courses, key=lambda c: c.id)
        out.append((m.meal_name, [(c.role, c.description) for c in ordered]))
    return out


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
