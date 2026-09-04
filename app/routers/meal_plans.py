from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.clients.base import AIClientBase
from app.clients.factory import get_ai_client
from app.core.deps import get_current_user
from app.db.session import get_db
import app.db.base  # noqa: F401 — register all models before relationship loaders
from app.models.meal_plan import MealCourseRole, MealPlanWeek, PlannedMeal, PlannedMealCourse
from app.models.user import User
from app.schemas.meal_plans import (
    MealPlanWeekCreate,
    MealPlanWeekRead,
    MealPlanWeekSummaryRead,
    MealPlanWeekUpdate,
    PlannedMealCourseCreate,
    PlannedMealRead,
    PlannedMealUpdate,
)
from app.services import recipe_service
from app.services.meal_plan_service import validate_meal_plan_week_dates
from app.services.usda_client import UsdaClient, get_usda_client


router = APIRouter(prefix="/meal-plans", tags=["meal-plans"])


def _plan_load():
    return (
        selectinload(MealPlanWeek.planned_meals)
        .selectinload(PlannedMeal.courses)
        .selectinload(PlannedMealCourse.planned_meal_recipes)
    )


def _meal_load():
    return selectinload(PlannedMeal.courses).selectinload(
        PlannedMealCourse.planned_meal_recipes
    )


def _summary_load():
    return (
        selectinload(MealPlanWeek.planned_meals),
        selectinload(MealPlanWeek.grocery_lists),
    )


def _to_summary(plan: MealPlanWeek) -> MealPlanWeekSummaryRead:
    return MealPlanWeekSummaryRead(
        id=plan.id,
        start_date=plan.start_date,
        end_date=plan.end_date,
        title=plan.title,
        created_at=plan.created_at,
        updated_at=plan.updated_at,
        meal_count=len(plan.planned_meals),
        has_grocery_list=len(plan.grocery_lists) > 0,
    )


def _add_planned_meal_courses(
    db: Session,
    meal: PlannedMeal,
    courses_in: list[PlannedMealCourseCreate] | None,
) -> None:
    if not courses_in:
        db.add(
            PlannedMealCourse(
                planned_meal_id=meal.id,
                role=MealCourseRole.entree,
                description=None,
            )
        )
        return
    for row in courses_in:
        db.add(
            PlannedMealCourse(
                planned_meal_id=meal.id,
                role=row.role,
                description=row.description,
            )
        )


@router.post("", response_model=MealPlanWeekRead, status_code=status.HTTP_201_CREATED)
def create_meal_plan_week(
    plan_in: MealPlanWeekCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> MealPlanWeek:
    try:
        validate_meal_plan_week_dates(plan_in.start_date, plan_in.end_date)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    plan = MealPlanWeek(
        user_id=current_user.id,
        start_date=plan_in.start_date,
        end_date=plan_in.end_date,
        title=plan_in.title,
    )
    db.add(plan)
    try:
        db.flush()  # ensure plan.id before creating meals
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A meal plan already exists for this week",
        ) from exc

    for meal_in in plan_in.planned_meals:
        meal = PlannedMeal(
            meal_plan_week_id=plan.id,
            day_index=meal_in.day_index,
            meal_name=meal_in.meal_name,
            status=meal_in.status,
        )
        db.add(meal)
        db.flush()
        _add_planned_meal_courses(db, meal, meal_in.courses)

    db.commit()
    return db.execute(
        select(MealPlanWeek).where(MealPlanWeek.id == plan.id).options(_plan_load())
    ).scalar_one()


@router.get("", response_model=List[MealPlanWeekSummaryRead])
def list_meal_plans(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[MealPlanWeekSummaryRead]:
    plans = list(
        db.execute(
            select(MealPlanWeek)
            .where(MealPlanWeek.user_id == current_user.id)
            .options(*_summary_load())
            .order_by(MealPlanWeek.start_date.desc())
        ).scalars().all()
    )
    return [_to_summary(plan) for plan in plans]


@router.get("/{plan_id}", response_model=MealPlanWeekRead)
def get_meal_plan(
    plan_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> MealPlanWeek:
    plan = db.execute(
        select(MealPlanWeek)
        .where(MealPlanWeek.id == plan_id, MealPlanWeek.user_id == current_user.id)
        .options(_plan_load())
    ).scalar_one_or_none()
    if plan is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Meal plan not found")
    return plan


@router.put("/{plan_id}", response_model=MealPlanWeekRead)
def update_meal_plan(
    plan_id: int,
    plan_in: MealPlanWeekUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> MealPlanWeek:
    plan = db.execute(
        select(MealPlanWeek).where(
            MealPlanWeek.id == plan_id, MealPlanWeek.user_id == current_user.id
        )
    ).scalar_one_or_none()
    if plan is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Meal plan not found")

    if plan_in.title is not None:
        plan.title = plan_in.title

    if plan_in.planned_meals is not None:
        for meal in db.execute(
            select(PlannedMeal).where(PlannedMeal.meal_plan_week_id == plan.id)
        ).scalars():
            db.delete(meal)
        db.flush()
        for meal_in in plan_in.planned_meals:
            meal = PlannedMeal(
                meal_plan_week_id=plan.id,
                day_index=meal_in.day_index,
                meal_name=meal_in.meal_name,
                status=meal_in.status,
            )
            db.add(meal)
            db.flush()
            _add_planned_meal_courses(db, meal, meal_in.courses)

    db.commit()
    return db.execute(
        select(MealPlanWeek).where(MealPlanWeek.id == plan.id).options(_plan_load())
    ).scalar_one()


@router.post("/{plan_id}/generate-recipes", response_model=MealPlanWeekRead)
def generate_recipes_for_plan(
    plan_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    ai_client: AIClientBase = Depends(get_ai_client),
    usda_client: UsdaClient = Depends(get_usda_client),
) -> MealPlanWeek:
    return recipe_service.generate_recipes_for_plan(
        plan_id, db, ai_client, current_user, usda_client
    )


@router.patch("/{plan_id}/meals/{meal_id}", response_model=PlannedMealRead)
def patch_planned_meal(
    plan_id: int,
    meal_id: int,
    body: PlannedMealUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    ai_client: AIClientBase = Depends(get_ai_client),
    usda_client: UsdaClient = Depends(get_usda_client),
) -> PlannedMeal:
    stmt = (
        select(PlannedMeal)
        .join(MealPlanWeek)
        .where(
            PlannedMeal.id == meal_id,
            PlannedMeal.meal_plan_week_id == plan_id,
            MealPlanWeek.user_id == current_user.id,
        )
        .options(_meal_load())
    )
    meal = db.execute(stmt).scalar_one_or_none()
    if meal is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Meal not found")

    if body.meal_name is None and body.status is None and body.courses is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="No fields to update",
        )

    if body.meal_name is not None:
        meal.meal_name = body.meal_name
    if body.status is not None:
        meal.status = body.status

    if body.courses is not None:
        recipe_service.sync_planned_meal_courses(
            db, ai_client, current_user, meal, body.courses, usda_client
        )

    db.commit()
    return db.execute(
        select(PlannedMeal).where(PlannedMeal.id == meal_id).options(_meal_load())
    ).scalar_one()


@router.post(
    "/{plan_id}/meals/{meal_id}/courses/{course_id}/generate-recipe",
    response_model=PlannedMealRead,
)
def generate_course_recipe(
    plan_id: int,
    meal_id: int,
    course_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    ai_client: AIClientBase = Depends(get_ai_client),
    usda_client: UsdaClient = Depends(get_usda_client),
) -> PlannedMeal:
    plan = db.execute(
        select(MealPlanWeek).where(
            MealPlanWeek.id == plan_id,
            MealPlanWeek.user_id == current_user.id,
        )
    ).scalar_one_or_none()
    if plan is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Meal plan not found")

    meal = db.execute(
        select(PlannedMeal).where(
            PlannedMeal.id == meal_id,
            PlannedMeal.meal_plan_week_id == plan_id,
        )
    ).scalar_one_or_none()
    if meal is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Meal not found")

    course = db.execute(
        select(PlannedMealCourse).where(
            PlannedMealCourse.id == course_id,
            PlannedMealCourse.planned_meal_id == meal_id,
        )
    ).scalar_one_or_none()
    if course is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found")

    recipe_service.generate_recipe_for_course(
        db, ai_client, current_user, meal, course, usda_client
    )
    db.commit()
    return db.execute(
        select(PlannedMeal).where(PlannedMeal.id == meal_id).options(_meal_load())
    ).scalar_one()

