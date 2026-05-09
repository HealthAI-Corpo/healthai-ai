import pytest
from unittest.mock import AsyncMock, MagicMock
from src.services.nutrition_service import enrich_with_nutrition

@pytest.mark.asyncio
async def test_enrich_with_nutrition_mapping():
    # 1. Simuler une détection YOLO
    mock_detections = [{"label": "bowl", "confidence": 0.9, "box": [0,0,10,10]}]
    
    # 2. Simuler la session de base de données
    mock_db = AsyncMock()
    
    # Simuler le résultat de l'exécution SQL
    mock_result = MagicMock()
    # On simule le comportement de .scalars().first()
    mock_result.scalars.return_value.first.return_value = MagicMock(
        nom="Oatmeal (1 cup cooked)",
        calories=160,
        proteines=6,
        glucides=28,
        lipides=3,
        eau_ml=0
    )
    
    # Configurer l'execute pour renvoyer notre mock_result
    mock_db.execute.return_value = mock_result
    
    # 3. Appel du service
    results = await enrich_with_nutrition(mock_detections, mock_db)
    
    # 4. Vérifications
    assert len(results) > 0
    assert results[0]["display_name"] == "Oatmeal (1 cup cooked)"
    assert results[0]["nutrition"]["calories"] == 160