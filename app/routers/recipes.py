from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.deps import get_current_user
from app.db.session import get_db
from app.models.meal_plan import PlannedMeal, PlannedMealRecipe
from app.models.nutrition import NutritionInfo
from app.models.recipe import Recipe, RecipeIngredient, RecipeStep
from app.models.user import User
from app.schemas.nutrition import NutritionInfoRead
from app.schemas.recipes import RecipeCreate, RecipeRead, RecipeSummaryRead, RecipeUpdate
from app.services import recipe_service
from app.services.ingredient_service import extract_preparation
from app.services.ingredient_service import get_or_create as get_or_create_ingredient


router = APIRouter(prefix="/recipes", tags=["recipes"])


@router.post("", response_model=RecipeRead, status_code=status.HTTP_201_CREATED)
def create_recipe(
    recipe_in: RecipeCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Recipe:
    recipe = Recipe(
        user_id=current_user.id,
        title=recipe_in.title,
        servings=recipe_in.servings,
    )
    db.add(recipe)
    db.flush()

    for step_in in recipe_in.steps:
        db.add(
            RecipeStep(
                recipe_id=recipe.id,
                step_number=step_in.step_number,
                text=step_in.text,
            )
        )

    for ingr_in in recipe_in.ingredients:
        base_name, preparation = extract_preparation(ingr_in.name)
        catalog = get_or_create_ingredient(db, base_name, ingr_in.category)
        db.add(
            RecipeIngredient(
                recipe_id=recipe.id,
                ingredient_id=catalog.id,
                quantity=ingr_in.quantity,
                unit=ingr_in.unit,
                preparation=preparation,
            )
        )

    db.commit()
    return recipe_service.get_owned_recipe(db, current_user, recipe.id)


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
) -> Recipe:
    return recipe_service.update_recipe(db, current_user, recipe_id, recipe_in)


@router.delete("/{recipe_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_recipe(
    recipe_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    recipe_service.delete_recipe(db, current_user, recipe_id)


@router.post("/{recipe_id}/nutrition", response_model=NutritionInfoRead, status_code=status.HTTP_201_CREATED)
def calculate_nutrition(
    recipe_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> NutritionInfo:
    recipe = recipe_service.get_owned_recipe(db, current_user, recipe_id)

    existing = db.execute(
        select(NutritionInfo).where(NutritionInfo.recipe_id == recipe.id)
    ).scalar_one_or_none()
    if existing is not None:
        db.delete(existing)
        db.flush()

    nutrition_info = NutritionInfo(
        recipe_id=recipe.id,
        per_serving=True,
        source="placeholder",
    )
    db.add(nutrition_info)
    db.commit()
    db.refresh(nutrition_info)
    return nutrition_info


@router.get("/{recipe_id}/nutrition", response_model=NutritionInfoRead)
def get_nutrition(
    recipe_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> NutritionInfo:
    recipe = recipe_service.get_owned_recipe(db, current_user, recipe_id)

    nutrition_info = db.execute(
        select(NutritionInfo).where(NutritionInfo.recipe_id == recipe.id)
    ).scalar_one_or_none()
    if nutrition_info is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Nutrition info not found for this recipe"
        )
    return nutrition_info
