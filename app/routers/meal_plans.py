from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.db.session import get_db
from app.models.meal_plan import MealPlanWeek, PlannedMeal
from app.models.user import User
from app.schemas.meal_plans import MealPlanWeekCreate, MealPlanWeekRead, MealPlanWeekUpdate


router = APIRouter(prefix="/meal-plans", tags=["meal-plans"])


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

    db.commit()
    db.refresh(plan)
    return plan


@router.get("", response_model=List[MealPlanWeekRead])
def list_meal_plans(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[MealPlanWeek]:
    plans = (
        db.query(MealPlanWeek)
        .filter(MealPlanWeek.user_id == current_user.id)
        .order_by(MealPlanWeek.start_date.desc())
        .all()
    )
    return plans


@router.get("/{plan_id}", response_model=MealPlanWeekRead)
def get_meal_plan(
    plan_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> MealPlanWeek:
    plan = (
        db.query(MealPlanWeek)
        .filter(MealPlanWeek.id == plan_id, MealPlanWeek.user_id == current_user.id)
        .first()
    )
    if not plan:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Meal plan not found")
    return plan


@router.put("/{plan_id}", response_model=MealPlanWeekRead)
def update_meal_plan(
    plan_id: int,
    plan_in: MealPlanWeekUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> MealPlanWeek:
    plan = (
        db.query(MealPlanWeek)
        .filter(MealPlanWeek.id == plan_id, MealPlanWeek.user_id == current_user.id)
        .first()
    )
    if not plan:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Meal plan not found")

    if plan_in.title is not None:
        plan.title = plan_in.title

    if plan_in.planned_meals is not None:
        # Simple strategy: delete existing meals and recreate from payload.
        db.query(PlannedMeal).filter(PlannedMeal.meal_plan_week_id == plan.id).delete()
        db.flush()
        for meal_in in plan_in.planned_meals:
            meal = PlannedMeal(
                meal_plan_week_id=plan.id,
                day_index=meal_in.day_index,
                meal_name=meal_in.meal_name,
                status=meal_in.status,
            )
            db.add(meal)

    db.commit()
    db.refresh(plan)
    return plan


# Stub endpoint for recipe generation; will later call Anthropic-backed service.
@router.post("/{plan_id}/generate-recipes", response_model=MealPlanWeekRead)
def generate_recipes_for_plan(
    plan_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> MealPlanWeek:
    plan = (
        db.query(MealPlanWeek)
        .filter(MealPlanWeek.id == plan_id, MealPlanWeek.user_id == current_user.id)
        .first()
    )
    if not plan:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Meal plan not found")

    # TODO: integrate with recipe_service + Anthropic to populate recipes for planned meals.

    return plan

