"""Recipe generation for meal plans via the AI client."""

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from fastapi import HTTPException, status

from app.clients.base import AIClientBase, MealGenerationMeal
from app.config import get_settings
from app.models.meal_plan import MealPlanWeek, PlannedMeal, PlannedMealCourse, PlannedMealRecipe
from app.models.recipe import Recipe, RecipeIngredient, RecipeStep
from app.models.user import User
from app.schemas.meal_plans import PlannedMealCourseUpsert
from app.schemas.recipes import RecipeCreate


def _persist_course_recipe(
    db: Session,
    user: User,
    meal: PlannedMeal,
    course: PlannedMealCourse,
    recipe_create: RecipeCreate,
) -> None:
    if recipe_create.role is not None and recipe_create.role != course.role:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="AI returned a recipe whose role does not match the course slot",
        )

    provider_label = get_settings().ai_provider.value

    recipe = Recipe(
        user_id=user.id,
        title=recipe_create.title,
        servings=recipe_create.servings,
        source_model=provider_label,
    )
    db.add(recipe)
    db.flush()

    for step in recipe_create.steps:
        db.add(
            RecipeStep(
                recipe_id=recipe.id,
                step_number=step.step_number,
                text=step.text,
            )
        )

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


def _clear_recipe_for_course_slot(db: Session, course_id: int) -> None:
    links = db.execute(
        select(PlannedMealRecipe).where(PlannedMealRecipe.planned_meal_course_id == course_id)
    ).scalars().all()
    recipe_ids = {link.recipe_id for link in links}
    for link in links:
        db.delete(link)
    db.flush()
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


def _delete_planned_meal_course_slot(db: Session, course: PlannedMealCourse) -> None:
    cid = course.id
    links = db.execute(
        select(PlannedMealRecipe).where(PlannedMealRecipe.planned_meal_course_id == cid)
    ).scalars().all()
    recipe_ids = {link.recipe_id for link in links}
    db.delete(course)
    db.flush()
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


def generate_recipe_for_course(
    db: Session,
    ai_client: AIClientBase,
    user: User,
    meal: PlannedMeal,
    course: PlannedMealCourse,
) -> None:
    _clear_recipe_for_course_slot(db, course.id)
    db.flush()

    generated = ai_client.generate_recipes([(meal.meal_name, [(course.role, course.description)])])
    if len(generated) != 1:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="AI returned a different number of recipes than course slots",
        )

    _persist_course_recipe(db, user, meal, course, generated[0])
    meal.status = "planned"


def sync_planned_meal_courses(
    db: Session,
    ai_client: AIClientBase,
    user: User,
    meal: PlannedMeal,
    incoming: list[PlannedMealCourseUpsert],
) -> None:
    if not incoming:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one course is required",
        )

    ids_in_payload = [x.id for x in incoming if x.id is not None]
    if len(ids_in_payload) != len(set(ids_in_payload)):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Duplicate course ids in request",
        )

    existing = {c.id: c for c in meal.courses}
    for cid in ids_in_payload:
        if cid not in existing:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Unknown course id for this meal",
            )

    incoming_id_set = set(ids_in_payload)
    for course in list(meal.courses):
        if course.id not in incoming_id_set:
            _delete_planned_meal_course_slot(db, course)

    db.refresh(meal)

    for item in incoming:
        if item.id is None:
            row = PlannedMealCourse(
                planned_meal_id=meal.id,
                role=item.role,
                description=item.description,
            )
            db.add(row)
            db.flush()
            generate_recipe_for_course(db, ai_client, user, meal, row)
            continue

        cur = db.get(PlannedMealCourse, item.id)
        if cur is None or cur.planned_meal_id != meal.id:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Course not found",
            )

        if cur.role != item.role:
            _delete_planned_meal_course_slot(db, cur)
            db.flush()
            row = PlannedMealCourse(
                planned_meal_id=meal.id,
                role=item.role,
                description=item.description,
            )
            db.add(row)
            db.flush()
            generate_recipe_for_course(db, ai_client, user, meal, row)
        elif cur.description != item.description:
            cur.description = item.description
            db.flush()
            generate_recipe_for_course(db, ai_client, user, meal, cur)


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

    gen_iter = iter(generated)
    for meal in meals:
        for course in sorted(meal.courses, key=lambda c: c.id):
            recipe_create = next(gen_iter)
            _persist_course_recipe(db, user, meal, course, recipe_create)
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
