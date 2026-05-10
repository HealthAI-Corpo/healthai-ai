"""
TEST D'INTÉGRATION : Flux complet et Sécurité
Ce fichier regroupe les tests de robustesse du service de vision :
1. test_analyze_endpoint_complete_flow : Vérifie que le JSON final contient
   toutes les données attendues (Detections, Totaux, Eau, Recommandations).
2. test_analyze_invalid_file : Vérifie que le système rejette proprement
   les fichiers dangereux ou invalides (ex: un .txt à la place d'une image).
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

    # Vérification de la présence des 3 piliers de la réponse HealthAI
    assert "detections" in data
    assert "total_repas" in data
    assert "recommandation" in data

    # Vérification spécifique du suivi d'hydratation (nouvelle fonctionnalité)
    assert "eau_ml" in data["total_repas"]


@pytest.mark.asyncio
async def test_analyze_invalid_file():
    # Simulation d'une erreur utilisateur : envoi d'un fichier texte
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        files = {"file": ("test.txt", b"not an image", "text/plain")}
        response = await ac.post("/analyze", files=files)

    # Le système doit répondre par une erreur 400 (Bad Request)
    assert response.status_code == 400
    assert "Format de fichier non supporté" in response.json()["detail"]
