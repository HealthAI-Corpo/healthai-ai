"""
TEST D'INTÉGRATION : Pipeline LLM avec Ollama (Qwen)
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.services.recommandation_service import generate_nutritional_advice_from_db


@pytest.mark.asyncio
async def test_llm_integration_with_mocked_prediction():
    # 1. On mocke l'accès à MongoDB
    with patch("src.services.recommandation_service.mongo_db") as mock_mongo:
        mock_cursor = AsyncMock()
        mock_cursor.__aiter__.return_value = []  # Aucun historique pour aujourd'hui
        mock_mongo.db.consumptions.find.return_value = mock_cursor

        # 2. On mocke la session PostgreSQL et le profil utilisateur
        mock_db = AsyncMock()
        mock_profil = MagicMock()
        mock_profil.poids_kg = 75
        mock_profil.objectif_principal = "Prise de masse"
        mock_profil.niveau_activite = "Intense"
        mock_profil.restrictions_alimentaires = "Aucune"

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_profil
        mock_db.execute.return_value = mock_result

        # 3. On mocke la fonction de prédiction commune pour simuler le retour strict de Qwen
        with patch(
            "src.services.recommandation_service.generate_llm_prediction", new_callable=AsyncMock
        ) as mock_llm:
            mock_llm.return_value = {
                "bilan_macros": "Votre apport est idéal pour votre objectif de prise de masse.",
                "conseils_sante": "Hydratez-vous bien après votre séance.",
            }

            # Appel de la fonction avec le nouveau nom correct !
            result = await generate_nutritional_advice_from_db(
                user_id=1, db_sql=mock_db, consumption_id="6a13684c67a8a0c84da543fb"
            )

            # Vérifications des nouvelles clés du schéma simplifié
            assert "bilan_macros" in result
            assert "conseils_sante" in result
            assert "prise de masse" in result["bilan_macros"].lower()
