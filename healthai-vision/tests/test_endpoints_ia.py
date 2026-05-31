"""Tests d'intégration : routes nutrition advice / suggestion (X-User-Id + ownership)."""

from unittest.mock import ANY, AsyncMock, MagicMock, patch

import pytest
from bson import ObjectId
from httpx import ASGITransport, AsyncClient

from src.main import app

CONSUMPTION_ID = "6a13684c67a8a0c84da543fb"
SUGGESTION_ID = "6a13684c67a8a0c84da543fc"


def _mongo_doc(user_id: str = "1", **extra) -> dict:
    doc = {"_id": ObjectId(CONSUMPTION_ID), "user_id": user_id, "summary": {}, "details": []}
    doc.update(extra)
    return doc


@pytest.mark.asyncio
async def test_advice_endpoint_async_trigger():
    """POST /nutrition/ai/advice avec X-User-Id valide → 200 processing."""
    with (
        patch("src.routers.nutrition_advice.mongo_db") as mock_mongo,
        patch("fastapi.BackgroundTasks.add_task"),
    ):
        mock_mongo.db.consumptions.find_one = AsyncMock(return_value=_mongo_doc())
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.post(
                "/nutrition/ai/advice",
                headers={"X-User-Id": "1"},
                json={"consumption_id": CONSUMPTION_ID},
            )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "processing"
    assert data["consumption_id"] == CONSUMPTION_ID


@pytest.mark.asyncio
async def test_advice_endpoint_forbidden_returns_404():
    """Repas appartenant à un autre user → 404 (silencieux)."""
    with patch("src.routers.nutrition_advice.mongo_db") as mock_mongo:
        mock_mongo.db.consumptions.find_one = AsyncMock(return_value=_mongo_doc(user_id="99"))
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.post(
                "/nutrition/ai/advice",
                headers={"X-User-Id": "1"},
                json={"consumption_id": CONSUMPTION_ID},
            )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_consumption_status_ownership():
    """GET /nutrition/consumption/{id} : refuse 404 si pas propriétaire."""
    with patch("src.routers.nutrition_advice.mongo_db") as mock_mongo:
        mock_mongo.db.consumptions.find_one = AsyncMock(return_value=_mongo_doc(user_id="99"))
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.get(
                f"/nutrition/consumption/{CONSUMPTION_ID}",
                headers={"X-User-Id": "1"},
            )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_suggest_meal_endpoint_async_trigger():
    with (
        patch("src.routers.nutrition_suggestion.mongo_db") as mock_mongo,
        patch("fastapi.BackgroundTasks.add_task"),
    ):
        mock_insert_result = MagicMock()
        mock_insert_result.inserted_id = SUGGESTION_ID
        mock_mongo.db.suggestions.insert_one = AsyncMock(return_value=mock_insert_result)

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.post("/nutrition/ai/suggest-meal", headers={"X-User-Id": "1"})
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "processing"
    assert data["suggestion_id"] == SUGGESTION_ID


@pytest.mark.asyncio
async def test_validate_suggestion_endpoint_success():
    mock_service_response = {
        "message": "Repas validé et inscrit avec succès dans PostgreSQL",
        "suggestion_id": SUGGESTION_ID,
    }
    with (
        patch("src.routers.nutrition_suggestion.mongo_db") as mock_mongo,
        patch(
            "src.routers.nutrition_suggestion.validate_and_log_meal_to_postgres",
            new_callable=AsyncMock,
            return_value=mock_service_response,
        ) as mock_service,
    ):
        mock_mongo.db.suggestions.find_one = AsyncMock(
            return_value={"_id": ObjectId(SUGGESTION_ID), "user_id": "1"}
        )
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.post(
                "/nutrition/ai/validate-suggestion",
                headers={"X-User-Id": "1"},
                json={"suggestion_id": SUGGESTION_ID},
            )
    assert response.status_code == 200
    data = response.json()
    assert "repas validé" in data["message"].lower()
    assert data["suggestion_id"] == SUGGESTION_ID
    mock_service.assert_called_once_with(SUGGESTION_ID, ANY)


@pytest.mark.asyncio
async def test_validate_suggestion_not_owner_returns_404():
    with patch("src.routers.nutrition_suggestion.mongo_db") as mock_mongo:
        mock_mongo.db.suggestions.find_one = AsyncMock(
            return_value={"_id": ObjectId(SUGGESTION_ID), "user_id": "99"}
        )
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.post(
                "/nutrition/ai/validate-suggestion",
                headers={"X-User-Id": "1"},
                json={"suggestion_id": SUGGESTION_ID},
            )
    assert response.status_code == 404
