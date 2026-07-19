from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
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
    MealPlanWeekUpdate,
    PlannedMealCourseCreate,
    PlannedMealRead,
    PlannedMealUpdate,
)
from app.services import recipe_service


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
    plan = MealPlanWeek(
        user_id=current_user.id,
        start_date=plan_in.start_date,
        end_date=plan_in.end_date,
        title=plan_in.title,
    )
    db.add(plan)
    db.flush()  # ensure plan.id before creating meals

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


@router.get("", response_model=List[MealPlanWeekRead])
def list_meal_plans(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[MealPlanWeek]:
    return list(
        db.execute(
            select(MealPlanWeek)
            .where(MealPlanWeek.user_id == current_user.id)
            .options(_plan_load())
            .order_by(MealPlanWeek.start_date.desc())
        ).scalars().all()
    )


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
) -> MealPlanWeek:
    return recipe_service.generate_recipes_for_plan(plan_id, db, ai_client, current_user)


@router.patch("/{plan_id}/meals/{meal_id}", response_model=PlannedMealRead)
def patch_planned_meal(
    plan_id: int,
    meal_id: int,
    body: PlannedMealUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    ai_client: AIClientBase = Depends(get_ai_client),
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
        recipe_service.sync_planned_meal_courses(db, ai_client, current_user, meal, body.courses)

    db.commit()
    return db.execute(
        select(PlannedMeal).where(PlannedMeal.id == meal_id).options(_meal_load())
    ).scalar_one()

