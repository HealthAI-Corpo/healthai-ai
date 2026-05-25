"""
TEST D'INTÉGRATION : Routes de conseils et suggestions asynchrones (Mocks isolés)
"""

from unittest.mock import ANY, AsyncMock, MagicMock, patch

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
        mock_mongo.db.suggestions.insert_one = AsyncMock(return_value=mock_insert_result)

        # 2. On mocke BackgroundTasks pour ne pas lancer le traitement SQL en tâche de fond
        with patch("fastapi.BackgroundTasks.add_task"):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as ac:
                payload = {"user_id": 1}
                response = await ac.post("/nutrition/ai/suggest-meal", json=payload)

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "processing"
    assert "suggestion_id" in data


@pytest.mark.asyncio
async def test_validate_suggestion_endpoint_success():
    """Vérifie le bon fonctionnement du nouvel endpoint de validation en isolant le service."""

    # 1. On prépare la réponse fictive que le service DOIT renvoyer à l'endpoint
    mock_service_response = {
        "message": "Repas validé et inscrit avec succès dans PostgreSQL",
        "suggestion_id": "6a13684c67a8a0c84da543fb",
    }

    # 2. On mocke directement la fonction du service appelée par l'endpoint.
    # En la remplaçant par un AsyncMock, elle ne s'exécutera pas et ne touchera
    # ni à Mongo ni à Postgres.
    with (
        patch(
            "src.main.validate_and_log_meal_to_postgres",
            new_callable=AsyncMock,
            return_value=mock_service_response,
        ) as mock_service,
        patch("src.main.mongo_db") as mock_main_mongo,
    ):
        # On neutralise le lifespan réseau au cas où
        mock_main_mongo.connect = MagicMock()
        mock_main_mongo.close = MagicMock()

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            payload = {"suggestion_id": "6a13684c67a8a0c84da543fb"}
            response = await ac.post("/nutrition/ai/validate-suggestion", json=payload)

    # 3. Vérifications des assertions de la route
    assert response.status_code == 200
    data = response.json()
    assert "repas validé" in data["message"].lower()
    assert data["suggestion_id"] == "6a13684c67a8a0c84da543fb"

    # On s'assure que l'endpoint a bien passé le bon ID au service
    mock_service.assert_called_once_with("6a13684c67a8a0c84da543fb", ANY)
