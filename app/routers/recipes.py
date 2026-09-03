from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.deps import get_current_user
from app.db.session import get_db
from app.models.meal_plan import PlannedMeal, PlannedMealRecipe
from app.models.nutrition import RecipeNutrition
from app.models.recipe import Recipe, RecipeIngredient
from app.models.user import User
from app.schemas.nutrition import RecipeNutritionRead
from app.schemas.recipes import RecipeCreate, RecipeRead, RecipeSummaryRead, RecipeUpdate
from app.services import recipe_service
from app.services.nutrition_service import ensure_and_calculate, get_recipe_nutrition
from app.services.usda_client import UsdaClient, get_usda_client


router = APIRouter(prefix="/recipes", tags=["recipes"])


@router.post("", response_model=RecipeRead, status_code=status.HTTP_201_CREATED)
def create_recipe(
    recipe_in: RecipeCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    usda_client: UsdaClient = Depends(get_usda_client),
) -> Recipe:
    return recipe_service.create_recipe(db, current_user, recipe_in, usda_client)


@router.get("", response_model=list[RecipeSummaryRead])
def list_recipes(
    search: str | None = Query(default=None),
    source_model: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[Recipe]:
    return recipe_service.list_recipes(
        db,
        current_user,
        search=search,
        source_model=source_model,
        page=page,
        page_size=page_size,
    )


@router.get("/meals/{meal_id}", response_model=list[RecipeRead])
def get_recipes_for_meal(
    meal_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[Recipe]:
    meal = db.execute(
        select(PlannedMeal)
        .join(PlannedMeal.meal_plan_week)
        .where(
            PlannedMeal.id == meal_id,
            PlannedMeal.meal_plan_week.has(user_id=current_user.id),
        )
    ).scalar_one_or_none()
    if meal is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Meal not found")

    links = db.execute(
        select(PlannedMealRecipe).where(PlannedMealRecipe.planned_meal_id == meal.id)
    ).scalars().all()
    if not links:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="No recipes for this meal"
        )

    recipe_ids = [link.recipe_id for link in links]
    recipes = db.execute(
        select(Recipe)
        .where(Recipe.id.in_(recipe_ids), Recipe.user_id == current_user.id)
        .options(
            selectinload(Recipe.steps),
            selectinload(Recipe.ingredients).selectinload(RecipeIngredient.ingredient),
        )
    ).scalars().all()
    if not recipes:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No recipes found")
    return list(recipes)


@router.get("/{recipe_id}", response_model=RecipeRead)
def get_recipe(
    recipe_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Recipe:
    return recipe_service.get_owned_recipe(db, current_user, recipe_id)


@router.put("/{recipe_id}", response_model=RecipeRead)
def update_recipe(
    recipe_id: int,
    recipe_in: RecipeUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    usda_client: UsdaClient = Depends(get_usda_client),
) -> Recipe:
    return recipe_service.update_recipe(db, current_user, recipe_id, recipe_in, usda_client)


@router.delete("/{recipe_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_recipe(
    recipe_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    recipe_service.delete_recipe(db, current_user, recipe_id)


@router.post("/{recipe_id}/nutrition", response_model=RecipeNutritionRead, status_code=status.HTTP_201_CREATED)
def calculate_nutrition(
    recipe_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    usda_client: UsdaClient = Depends(get_usda_client),
) -> RecipeNutrition:
    recipe = recipe_service.get_owned_recipe(db, current_user, recipe_id)
    nutrition = ensure_and_calculate(db, recipe, usda_client)
    db.commit()
    db.refresh(nutrition)
    return nutrition


@router.get("/{recipe_id}/nutrition", response_model=RecipeNutritionRead)
def get_nutrition(
    recipe_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> RecipeNutrition:
    recipe = recipe_service.get_owned_recipe(db, current_user, recipe_id)
    nutrition = get_recipe_nutrition(db, recipe)
    if nutrition is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Nutrition info not found for this recipe"
        )
    return nutrition
