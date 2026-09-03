from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Protocol

import httpx
from fastapi import Depends

from app.config import Settings, get_settings

logger = logging.getLogger("meal_planner")

FDC_BASE_URL = "https://api.nal.usda.gov/fdc/v1"
_SEARCH_DATA_TYPES = ["Foundation", "SR Legacy", "Survey (FNDDS)"]


@dataclass(frozen=True)
class UsdaFoodResult:
    fdc_id: int
    name: str
    nutrient_data: list[dict[str, Any]]
    source_version: str | None


class UsdaClient(Protocol):
    def fetch_food(self, ingredient_name: str) -> UsdaFoodResult | None: ...


class FdcUsdaClient:
    def __init__(self, api_key: str) -> None:
        self._api_key = api_key

    def fetch_food(self, ingredient_name: str) -> UsdaFoodResult | None:
        try:
            with httpx.Client(timeout=30.0) as client:
                # POST body — GET with repeated dataType query params is rejected by FDC/nginx (400).
                search = client.post(
                    f"{FDC_BASE_URL}/foods/search",
                    params={"api_key": self._api_key},
                    json={
                        "query": ingredient_name,
                        "pageSize": 5,
                        "dataType": _SEARCH_DATA_TYPES,
                    },
                )
                search.raise_for_status()
                foods = search.json().get("foods") or []
                if not foods:
                    return None
                fdc_id = int(foods[0]["fdcId"])
                detail = client.get(
                    f"{FDC_BASE_URL}/food/{fdc_id}",
                    params={"api_key": self._api_key},
                )
                detail.raise_for_status()
                payload = detail.json()
        except httpx.HTTPError as exc:
            logger.warning(
                "USDA lookup failed for ingredient %s: %s",
                ingredient_name,
                exc,
            )
            return None

        nutrients: list[dict[str, Any]] = []
        for entry in payload.get("foodNutrients") or []:
            nutrient = entry.get("nutrient") or {}
            amount = entry.get("amount")
            if amount is None:
                amount = entry.get("value")
            nutrient_id = nutrient.get("id")
            if nutrient_id is None:
                nutrient_id = entry.get("nutrientId")
            if amount is None or nutrient_id is None:
                continue
            nutrients.append(
                {
                    "nutrient_id": nutrient_id,
                    "name": nutrient.get("name") or entry.get("nutrientName"),
                    "unit": nutrient.get("unitName") or entry.get("unitName"),
                    "amount": amount,
                }
            )

        source_version = payload.get("publicationDate") or payload.get("dataType")
        if source_version is not None:
            source_version = str(source_version)

        return UsdaFoodResult(
            fdc_id=fdc_id,
            name=ingredient_name,
            nutrient_data=nutrients,
            source_version=source_version,
        )


class FakeUsdaClient:
    def __init__(self, foods: dict[str, UsdaFoodResult] | None = None) -> None:
        self.foods = foods or {}
        self.recorded_calls: list[str] = []

    def fetch_food(self, ingredient_name: str) -> UsdaFoodResult | None:
        self.recorded_calls.append(ingredient_name)
        return self.foods.get(ingredient_name)


def build_usda_client(settings: Settings | None = None) -> UsdaClient:
    settings = settings or get_settings()
    if not settings.usda_api_key:
        return FakeUsdaClient()
    return FdcUsdaClient(api_key=settings.usda_api_key)


def get_usda_client(settings: Settings = Depends(get_settings)) -> UsdaClient:
    return build_usda_client(settings)
