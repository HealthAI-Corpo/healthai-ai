"""
TEST UNITAIRE : Service de Recommandation
Ce test vérifie l'intelligence nutritionnelle du système :
1. On simule un profil utilisateur avec un objectif de "Perte de poids".
2. On simule un historique de consommation vide dans MongoDB.
3. On vérifie que l'algorithme calcule bien le besoin calorique théorique
   MOINS le déficit de 500 kcal (Déficit de perte de poids).
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.services.recommandation_service import generate_nutritional_advice


@pytest.mark.asyncio
async def test_recommendation_weight_loss():
    # On mocke l'accès à MongoDB avant d'appeler le service
    with patch("src.services.recommandation_service.mongo_db") as mock_mongo:
        # Configuration du mock Mongo
        mock_cursor = AsyncMock()
        # On simule qu'on n'a rien mangé encore (liste vide)
        mock_cursor.__aiter__.return_value = []
        mock_mongo.db.consumptions.find.return_value = mock_cursor

        # Mock SQL
        mock_db = AsyncMock()
        mock_profil = MagicMock()
        mock_profil.poids_kg = 80
        mock_profil.objectif_principal = "Perte de poids"
        mock_profil.niveau_activite = "Modéré"

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_profil
        mock_db.execute.return_value = mock_result

        # Appel du service
        advice = await generate_nutritional_advice(user_id=1, db_sql=mock_db)

        assert "kcal" in advice
        # Vérifie que le déficit est bien pris en compte (80*30*1.4 - 500 = 2860)
        assert "2860" in advice
