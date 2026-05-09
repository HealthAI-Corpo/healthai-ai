import io

import pytest
from httpx import ASGITransport, AsyncClient
from PIL import Image

from src.main import app


@pytest.mark.asyncio
async def test_analyze_endpoint_complete_flow():
    """
    Test d'intégration qui vérifie que l'API analyse l'image et
    renvoie la structure complète incluant nutrition et recommandation.
    """
    # 1. Création d'une image factice valide (640x640 pour YOLO)
    img = Image.new("RGB", (640, 640), color="white")
    img_byte_arr = io.BytesIO()
    img.save(img_byte_arr, format="JPEG")
    img_bytes = img_byte_arr.getvalue()

    # 2. Utilisation du transport ASGI pour FastAPI
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        files = {"file": ("test.jpg", img_bytes, "image/jpeg")}
        # On teste avec l'utilisateur 1 (celui qu'on a configuré dans Postgres)
        response = await ac.post("/analyze?user_id=1", files=files)

    # 3. Vérifications de base
    assert response.status_code == 200
    data = response.json()

    # 4. Vérification de la structure de réponse enrichie
    assert "detections" in data
    assert "total_repas" in data
    assert "recommandation" in data

    # 5. Vérification des champs nutritionnels dans total_repas
    total = data["total_repas"]
    assert "calories" in total
    assert "eau_ml" in total  # On vérifie que notre nouvelle clé est présente

    # 6. Vérification du format des détections (si YOLO en trouve)
    if len(data["detections"]) > 0:
        first_det = data["detections"][0]
        assert "display_name" in first_det
        assert "nutrition" in first_det
        # On vérifie que l'eau est bien présente dans le détail nutritionnel
        assert "eau" in first_det["nutrition"] or "eau_ml" in first_det["nutrition"]


@pytest.mark.asyncio
async def test_analyze_invalid_file():
    """Vérifie que le système rejette les fichiers qui ne sont pas des images."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        files = {"file": ("test.txt", b"not an image", "text/plain")}
        response = await ac.post("/analyze", files=files)

    assert response.status_code == 400
    assert "Format de fichier non supporté" in response.json()["detail"]
