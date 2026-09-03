from unittest.mock import MagicMock, patch

from app.services.usda_client import FdcUsdaClient, FakeUsdaClient, UsdaFoodResult


def test_fake_records_calls_and_returns_mapped_food():
    food = UsdaFoodResult(fdc_id=1, name="carrot", nutrient_data=[], source_version=None)
    client = FakeUsdaClient(foods={"carrot": food})

    assert client.fetch_food("carrot") is food
    assert client.fetch_food("unknown") is None
    assert client.recorded_calls == ["carrot", "unknown"]


def test_fdc_client_searches_then_loads_food():
    search_resp = MagicMock()
    search_resp.json.return_value = {"foods": [{"fdcId": 171077}]}
    search_resp.raise_for_status = MagicMock()

    detail_resp = MagicMock()
    detail_resp.json.return_value = {
        "publicationDate": "2024-10-31",
        "foodNutrients": [
            {
                "nutrient": {"id": 1008, "name": "Energy", "unitName": "KCAL"},
                "amount": 165.0,
            }
        ],
    }
    detail_resp.raise_for_status = MagicMock()

    mock_client = MagicMock()
    mock_client.post.return_value = search_resp
    mock_client.get.return_value = detail_resp
    mock_client.__enter__.return_value = mock_client
    mock_client.__exit__.return_value = False

    with patch("app.services.usda_client.httpx.Client", return_value=mock_client):
        result = FdcUsdaClient(api_key="test-key").fetch_food("chicken breast")

    assert result is not None
    assert result.fdc_id == 171077
    assert result.name == "chicken breast"
    assert result.source_version == "2024-10-31"
    assert result.nutrient_data == [
        {"nutrient_id": 1008, "name": "Energy", "unit": "KCAL", "amount": 165.0}
    ]
    mock_client.post.assert_called_once()
    mock_client.get.assert_called_once()
    post_kwargs = mock_client.post.call_args.kwargs
    assert post_kwargs["json"]["query"] == "chicken breast"
    assert post_kwargs["json"]["dataType"] == ["Foundation", "SR Legacy", "Survey (FNDDS)"]


def test_fdc_client_returns_none_on_http_error():
    import httpx

    mock_client = MagicMock()
    mock_client.post.side_effect = httpx.ConnectError("boom")
    mock_client.__enter__.return_value = mock_client
    mock_client.__exit__.return_value = False

    with patch("app.services.usda_client.httpx.Client", return_value=mock_client):
        result = FdcUsdaClient(api_key="test-key").fetch_food("chicken breast")

    assert result is None


def test_fdc_client_parses_flat_nutrient_shape():
    search_resp = MagicMock()
    search_resp.json.return_value = {"foods": [{"fdcId": 99}]}
    search_resp.raise_for_status = MagicMock()

    detail_resp = MagicMock()
    detail_resp.json.return_value = {
        "dataType": "SR Legacy",
        "foodNutrients": [
            {
                "nutrientId": 1008,
                "nutrientName": "Energy",
                "unitName": "KCAL",
                "value": 41.0,
            }
        ],
    }
    detail_resp.raise_for_status = MagicMock()

    mock_client = MagicMock()
    mock_client.post.return_value = search_resp
    mock_client.get.return_value = detail_resp
    mock_client.__enter__.return_value = mock_client
    mock_client.__exit__.return_value = False

    with patch("app.services.usda_client.httpx.Client", return_value=mock_client):
        result = FdcUsdaClient(api_key="test-key").fetch_food("carrot")

    assert result is not None
    assert result.nutrient_data == [
        {"nutrient_id": 1008, "name": "Energy", "unit": "KCAL", "amount": 41.0}
    ]
