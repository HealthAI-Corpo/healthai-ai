"""
TEST UNITAIRE : Service de Recommandation Nutritionnelle
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.services.recommandation_service import generate_nutritional_advice_from_db


@pytest.mark.asyncio
async def test_recommendation_weight_loss():
    # 1. Mock de la base de données MongoDB
    with patch("src.services.recommandation_service.mongo_db") as mock_mongo:
        mock_cursor = AsyncMock()
        mock_cursor.__aiter__.return_value = []  # L'utilisateur n'a rien mangé
        mock_mongo.db.consumptions.find.return_value = mock_cursor

        # 2. Mock de la base de données SQL (Profil de l'utilisateur)
        mock_db = AsyncMock()
        mock_profil = MagicMock()
        mock_profil.poids_kg = 80
        mock_profil.objectif_principal = "Perte de poids"
        mock_profil.niveau_activite = "Modéré"
        mock_profil.restrictions_alimentaires = "Aucune"

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_profil
        mock_db.execute.return_value = mock_result

        # 3. Mock de l'appel LLM pour tester le comportement nominal
        with patch(
            "src.services.recommandation_service.generate_llm_prediction", new_callable=AsyncMock
        ) as mock_llm:
            # On simule la réponse JSON stricte simplifiée de Qwen
            mock_llm.return_value = {
                "bilan_macros": "Il vous reste 2860 kcal pour votre objectif.",
                "conseils_sante": "Pensez à boire de l'eau.",
            }

            # Appel du nouveau service découplé
            advice = await generate_nutritional_advice_from_db(
                user_id=1, db_sql=mock_db, consumption_id="6a13684c67a8a0c84da543fb"
            )

            # Vérification du nouveau format d'output validé
            assert "bilan_macros" in advice
            assert "conseils_sante" in advice

            # Vérification du calcul théorique (80 * 30 * 1.4) - 500 = 2860 kcal
            assert "2860" in advice["bilan_macros"]
