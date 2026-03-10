from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.db.session import get_db
from app.models.meal_plan import PlannedMeal, PlannedMealRecipe
from app.models.recipe import Recipe, RecipeIngredient
from app.models.user import User
from app.schemas.recipes import RecipeCreate, RecipeRead


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
        instructions=recipe_in.instructions,
        servings=recipe_in.servings,
    )
    db.add(recipe)
    db.flush()

    for ingr_in in recipe_in.ingredients:
        ingredient = RecipeIngredient(
            recipe_id=recipe.id,
            name=ingr_in.name,
            quantity=ingr_in.quantity,
            unit=ingr_in.unit,
            category=ingr_in.category,
        )
        db.add(ingredient)

    db.commit()
    db.refresh(recipe)
    return recipe


@router.get("/{recipe_id}", response_model=RecipeRead)
def get_recipe(
    recipe_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Recipe:
    recipe = (
        db.query(Recipe)
        .filter(Recipe.id == recipe_id, Recipe.user_id == current_user.id)
        .first()
    )
    if not recipe:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recipe not found")
    return recipe


@router.get("/meals/{meal_id}", response_model=list[RecipeRead])
def get_recipes_for_meal(
    meal_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[Recipe]:
    meal = (
        db.query(PlannedMeal)
        .join(PlannedMeal.meal_plan_week)
        .filter(
            PlannedMeal.id == meal_id,
            PlannedMeal.meal_plan_week.has(user_id=current_user.id),
        )
        .first()
    )
    if not meal:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Meal not found")

    links = (
        db.query(PlannedMealRecipe)
        .filter(PlannedMealRecipe.planned_meal_id == meal.id)
        .all()
    )
    if not links:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="No recipes for this meal"
        )

    recipe_ids = [link.recipe_id for link in links]
    recipes = (
        db.query(Recipe)
        .filter(Recipe.id.in_(recipe_ids), Recipe.user_id == current_user.id)
        .all()
    )
    if not recipes:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No recipes found")
    return recipes

