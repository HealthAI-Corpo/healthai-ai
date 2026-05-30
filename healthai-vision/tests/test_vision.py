"""Tests d'intégration : flux /analyze (YOLO mocké, X-User-Id requis)."""

import io
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient
from PIL import Image

from src.main import app
from src.routers.analyze import _get_db_sql


@pytest.mark.asyncio
async def test_analyze_endpoint_complete_flow():
    mock_db_session = AsyncMock()
    app.dependency_overrides[_get_db_sql] = lambda: mock_db_session

    img = Image.new("RGB", (640, 640), color="white")
    img_byte_arr = io.BytesIO()
    img.save(img_byte_arr, format="JPEG")
    img_bytes = img_byte_arr.getvalue()

    with (
        patch("src.routers.analyze.mongo_db") as mock_mongo,
        patch("src.routers.analyze.enrich_with_nutrition", AsyncMock(return_value=[])),
    ):
        mock_insert_result = MagicMock()
        mock_insert_result.inserted_id = "6a13684c67a8a0c84da543fb"
        mock_mongo.db.consumptions.insert_one = AsyncMock(return_value=mock_insert_result)

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            files = {"file": ("test.jpg", img_bytes, "image/jpeg")}
            response = await ac.post("/analyze", headers={"X-User-Id": "1"}, files=files)

    app.dependency_overrides.clear()

    assert response.status_code == 200
    data = response.json()
    assert "detections" in data
    assert "total_repas" in data
    assert "consumption_id" in data
    assert "eau_ml" in data["total_repas"]
    assert data["user_id"] == "1"


@pytest.mark.asyncio
async def test_analyze_invalid_file():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        files = {"file": ("test.txt", b"not an image", "text/plain")}
        response = await ac.post("/analyze", headers={"X-User-Id": "1"}, files=files)
    assert response.status_code == 400
    assert "Format de fichier non supporté" in response.json()["detail"]


@pytest.mark.asyncio
async def test_analyze_missing_user_header():
    """X-User-Id absent (devrait être injecté par la gateway) → 422."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        files = {"file": ("test.txt", b"not an image", "text/plain")}
        response = await ac.post("/analyze", files=files)
    assert response.status_code == 422
