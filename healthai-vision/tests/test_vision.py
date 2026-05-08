import pytest
from httpx import AsyncClient, ASGITransport 
from src.main import app
import io
from PIL import Image

@pytest.mark.asyncio
async def test_analyze_endpoint():
    # 1. Création d'une image factice valide
    img = Image.new('RGB', (100, 100), color='red')
    img_byte_arr = io.BytesIO()
    img.save(img_byte_arr, format='JPEG')
    img_bytes = img_byte_arr.getvalue()

    # 2. Utilisation du transport ASGIPour FastAPI
    transport = ASGITransport(app=app)
    
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        files = {'file': ('test.jpg', img_bytes, 'image/jpeg')}
        response = await ac.post("/analyze", files=files)
    
    # 3. Vérifications
    assert response.status_code == 200
    data = response.json()
    assert "detections" in data