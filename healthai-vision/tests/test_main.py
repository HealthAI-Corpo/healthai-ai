import pytest
from httpx import AsyncClient, ASGITransport 
from src.main import app
import io
from PIL import Image

@pytest.mark.asyncio
async def test_analyze_meal_integration():
    # Création d'une image factice
    img = Image.new('RGB', (640, 640), color='white')
    img_byte_arr = io.BytesIO()
    img.save(img_byte_arr, format='JPEG')
    img_bytes = img_byte_arr.getvalue()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        files = {'file': ('test.jpg', img_bytes, 'image/jpeg')}
        # On passe un user_id existant dans ta base de test
        response = await ac.post("/analyze?user_id=1", files=files)
    
    assert response.status_code == 200
    data = response.json()
    assert "total_repas" in data
    assert "recommandation" in data
    assert isinstance(data["total_repas"]["calories"], (int, float))