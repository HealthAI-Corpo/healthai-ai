"""
TEST D'INTÉGRATION : Routes de conseils et suggestions asynchrones (Mocks isolés)
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from src.main import app


@pytest.mark.asyncio
async def test_advice_endpoint_async_trigger():
    # On mocke BackgroundTasks pour empêcher l'exécution de la vraie fonction SQL/Mongo
    with patch("fastapi.BackgroundTasks.add_task"):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            payload = {"user_id": 1, "consumption_id": "6a13684c67a8a0c84da543fb"}
            response = await ac.post("/nutrition/ai/advice", json=payload)

    # La route doit répondre IMMÉDIATEMENT avec le statut de traitement
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "processing"
    assert "consumption_id" in data


@pytest.mark.asyncio
async def test_suggest_meal_endpoint_async_trigger():
    # 1. On mocke complètement MongoDB pour la création du document temporaire
    with patch("src.main.mongo_db") as mock_mongo:
        mock_insert_result = MagicMock()
        mock_insert_result.inserted_id = "6a13684c67a8a0c84da543fb"

        # On utilise un AsyncMock pour le insert_one de Mongo afin qu'il soit attendable (await)
        mock_mongo.db.suggestions.insert_one = AsyncMock(return_value=mock_insert_result)

        # 2. On mocke BackgroundTasks pour ne pas lancer le traitement SQL en tâche de fond
        with patch("fastapi.BackgroundTasks.add_task"):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as ac:
                payload = {"user_id": 1}
                response = await ac.post("/nutrition/ai/suggest-meal", json=payload)

    # La route doit valider la création de la tâche de fond sans toucher à PostgreSQL
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "processing"
    assert "suggestion_id" in data
