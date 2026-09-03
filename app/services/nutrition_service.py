from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.ingredient import Ingredient
from app.models.nutrition import IngredientNutrition, RecipeNutrition
from app.models.recipe import Recipe, RecipeIngredient
from app.services.usda_client import UsdaClient, build_usda_client

MACRO_NUTRIENT_IDS: dict[str, tuple[int, ...]] = {
    "calories": (1008,),
    "protein_g": (1003,),
    "carbs_g": (1005,),
    "fat_g": (1004,),
    "fiber_g": (1079,),
    # Foundation often uses 1063 ("Sugars, Total"); Survey/SR Legacy use 2000 ("Total Sugars").
    "sugar_g": (2000, 1063),
    "sodium_mg": (1093,),
}

_MASS_UNITS = frozenset({"gram", "g", "grams"})
_KG_UNITS = frozenset({"kilogram", "kilograms", "kg"})
_VOLUME_ML_UNITS = frozenset(
    {"ml", "millilitre", "milliliter", "millilitres", "milliliters"}
)
_LITRE_UNITS = frozenset({"litre", "liter", "l"})


def _scale_factor(quantity: Decimal | float | None, unit: str | None) -> float | None:
    if quantity is None or unit is None:
        return None
    qty = float(quantity)
    normalized = unit.lower().strip()
    if normalized in _MASS_UNITS or normalized in _VOLUME_ML_UNITS:
        return qty / 100.0
    if normalized in _KG_UNITS:
        return qty * 10.0
    if normalized in _LITRE_UNITS:
        return qty * 10.0
    return None


def _amount_for_nutrient(nutrient_data: list[dict], nutrient_ids: tuple[int, ...]) -> float | None:
    for item in nutrient_data:
        raw_id = item.get("nutrient_id")
        try:
            if raw_id is None or int(raw_id) not in nutrient_ids:
                continue
        except (TypeError, ValueError):
            continue
        amount = item.get("amount")
        if amount is None:
            return None
        return float(amount)
    return None


def ensure_and_calculate(
    db: Session,
    recipe: Recipe,
    usda_client: UsdaClient | None = None,
) -> RecipeNutrition:
    client = usda_client or build_usda_client()
    db.flush()

    lines = list(
        db.execute(
            select(RecipeIngredient)
            .where(RecipeIngredient.recipe_id == recipe.id)
            .options(selectinload(RecipeIngredient.ingredient))
        ).scalars().all()
    )
    ingredient_ids = {line.ingredient_id for line in lines}

    existing_rows: dict[int, IngredientNutrition] = {}
    if ingredient_ids:
        existing_rows = {
            row.ingredient_id: row
            for row in db.execute(
                select(IngredientNutrition).where(
                    IngredientNutrition.ingredient_id.in_(ingredient_ids)
                )
            ).scalars().all()
        }

    missing_ids = ingredient_ids - existing_rows.keys()
    if missing_ids:
        ingredients = {
            row.id: row
            for row in db.execute(
                select(Ingredient).where(Ingredient.id.in_(missing_ids))
            ).scalars().all()
        }
        now = datetime.now(timezone.utc)
        for iid in missing_ids:
            ingredient = ingredients[iid]
            result = client.fetch_food(ingredient.name)
            if result is None:
                continue
            row = IngredientNutrition(
                fdc_id=result.fdc_id,
                ingredient_id=ingredient.id,
                name=ingredient.name,
                nutrient_data_json=result.nutrient_data,
                fetched_at=now,
                last_checked=now,
                source_version=result.source_version,
            )
            db.add(row)
            existing_rows[iid] = row
        db.flush()

    per_serving = recipe.servings is not None and recipe.servings > 0
    divisor = float(recipe.servings) if per_serving else 1.0

    # Skip lines that cannot be scaled (missing unit/cache, count units like piece/whole).
    # Partial totals are preferred over nulling the whole recipe for one bad line.
    scaled_nutrients: list[tuple[list[dict], float]] = []
    for line in lines:
        cache = existing_rows.get(line.ingredient_id)
        factor = _scale_factor(line.quantity, line.unit)
        if cache is None or factor is None:
            continue
        scaled_nutrients.append((cache.nutrient_data_json or [], factor))

    macros: dict[str, float | None] = {key: None for key in MACRO_NUTRIENT_IDS}
    micros: list[dict] | None = None
    macro_id_set = {nid for ids in MACRO_NUTRIENT_IDS.values() for nid in ids}

    if scaled_nutrients:
        for field, nutrient_ids in MACRO_NUTRIENT_IDS.items():
            total = 0.0
            saw_any = False
            for data, factor in scaled_nutrients:
                amount = _amount_for_nutrient(data, nutrient_ids)
                if amount is None:
                    # Missing on this food → contribute 0 (e.g. sugar has no fiber).
                    continue
                saw_any = True
                total += amount * factor
            macros[field] = (total / divisor) if saw_any else None

        micro_totals: dict[int, dict] = {}
        for data, factor in scaled_nutrients:
            for item in data:
                raw_id = item.get("nutrient_id")
                try:
                    nid = int(raw_id) if raw_id is not None else None
                except (TypeError, ValueError):
                    nid = None
                if nid is None or nid in macro_id_set:
                    continue
                amount = item.get("amount")
                if amount is None:
                    continue
                bucket = micro_totals.setdefault(
                    nid,
                    {
                        "nutrient_id": nid,
                        "name": item.get("name"),
                        "unit": item.get("unit"),
                        "amount": 0.0,
                    },
                )
                bucket["amount"] += float(amount) * factor
        micros = [
            {**item, "amount": item["amount"] / divisor}
            for item in micro_totals.values()
        ]

    nutrition = db.execute(
        select(RecipeNutrition).where(RecipeNutrition.recipe_id == recipe.id)
    ).scalar_one_or_none()
    if nutrition is None:
        nutrition = RecipeNutrition(recipe_id=recipe.id)
        db.add(nutrition)

    nutrition.calories = macros["calories"]
    nutrition.protein_g = macros["protein_g"]
    nutrition.carbs_g = macros["carbs_g"]
    nutrition.fat_g = macros["fat_g"]
    nutrition.fiber_g = macros["fiber_g"]
    nutrition.sugar_g = macros["sugar_g"]
    nutrition.sodium_mg = macros["sodium_mg"]
    nutrition.micro_nutrients_json = micros
    nutrition.per_serving = per_serving
    nutrition.source = "usda"
    db.flush()
    return nutrition


def get_recipe_nutrition(db: Session, recipe: Recipe) -> RecipeNutrition | None:
    return db.execute(
        select(RecipeNutrition).where(RecipeNutrition.recipe_id == recipe.id)
    ).scalar_one_or_none()
