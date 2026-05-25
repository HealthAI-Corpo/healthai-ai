"""
TEST D'INTÉGRATION : Flux de vision et Sécurité
"""

import io

import pytest
from httpx import ASGITransport, AsyncClient
from PIL import Image

from src.main import app


@pytest.mark.asyncio
async def test_analyze_endpoint_complete_flow():
    # Préparation de l'image de test
    img = Image.new("RGB", (640, 640), color="white")
    img_byte_arr = io.BytesIO()
    img.save(img_byte_arr, format="JPEG")
    img_bytes = img_byte_arr.getvalue()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        files = {"file": ("test.jpg", img_bytes, "image/jpeg")}
        response = await ac.post("/analyze?user_id=1", files=files)

    assert response.status_code == 200
    data = response.json()

    # Vérification des piliers après découplage
    assert "detections" in data
    assert "total_repas" in data
    assert "consumption_id" in data  # 🌟 Crucial pour le polling asynchrone

    # Vérification spécifique du suivi d'hydratation
    assert "eau_ml" in data["total_repas"]


@pytest.mark.asyncio
async def test_analyze_invalid_file():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        files = {"file": ("test.txt", b"not an image", "text/plain")}
        response = await ac.post("/analyze", files=files)

    assert response.status_code == 400
    assert "Format de fichier non supporté" in response.json()["detail"]
