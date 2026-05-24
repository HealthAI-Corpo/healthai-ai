import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import respx
from healthai_common.llm import generate_llm_prediction
from httpx import Response

from src.services.recommandation_service import generate_nutritional_advice


# =====================================================================
# 1. TEST UNITAIRE : Fonction commune de prédiction LLM (healthai_common)
# =====================================================================
@pytest.mark.asyncio
@respx.mock
async def test_generate_llm_prediction_success():
    """Vérifie que la fonction commune appelle correctement l'API Ollama
    et nettoie le format brut s'il contient des balises Markdown.
    """
    # En ne mettant que la fin de l'URL, respx intercepte TOUTES les bases d'URL
    # (que ce soit localhost, healthai-ollama, ou n'importe quoi d'autre)
    route = respx.post(path="/api/generate").mock(
        return_value=Response(
            200,
            json={
                "response": (
                    '{\n"statut_motivation": "Super boulot !",\n'
                    '"analyse_macros": "Tout est au vert.",\n'
                    '"recommandation_repas": "Un poulet aux légumes.",\n'
                    '"alerte_eau": "Buvez de l\'eau."\n}'
                )
            },
        )
    )

    result = await generate_llm_prediction(
        base_url="http://healthai-ollama:11434",  # On utilise la même URL que le service
        model_name="llama3.2:1b",
        system_prompt="Tu es un assistant.",
        user_prompt="Bonjour",
    )

    assert route.called
    assert result["statut_motivation"] == "Super boulot !"
    assert result["recommandation_repas"] == "Un poulet aux légumes."


@pytest.mark.asyncio
@respx.mock
async def test_generate_llm_prediction_invalid_json():
    """Vérifie que le système lève une erreur (ValueError ou JSONDecodeError)
    lorsque le LLM renvoie un contenu qui n'est pas du JSON valide.
    """

    # On simule une réponse cassée qui fera planter n'importe quel décodeur
    respx.post(path="/api/generate").mock(
        return_value=Response(200, text='{"response": "Texte invalide sans fermeture')
    )

    # On s'attend à ce que le code lève une exception (la tienne ou celle de Python)
    # Plus besoin de variable 'exc' ou d'assert en dessous, pytest gère tout tout seul !
    with pytest.raises((ValueError, json.JSONDecodeError)):
        await generate_llm_prediction(
            base_url="http://healthai-ollama:11434",
            model_name="model",
            system_prompt="Prompt",
            user_prompt="User",
        )


# =====================================================================
# 2. TEST UNITAIRE : Service de Recommandation avec simulation LLM
# =====================================================================
@pytest.mark.asyncio
@patch("src.services.recommandation_service.generate_llm_prediction", new_callable=AsyncMock)
@patch("src.services.recommandation_service.mongo_db")
async def test_generate_nutritional_advice_with_llm_success(mock_mongo, mock_llm):
    """Vérifie que le service de recommandation intègre bien le résultat du LLM
    lorsque l'appel à la fonction partagée réussit.
    """
    mock_cursor = AsyncMock()
    mock_cursor.__aiter__.return_value = []
    mock_mongo.db.consumptions.find.return_value = mock_cursor

    mock_db = AsyncMock()
    mock_profil = MagicMock()
    mock_profil.poids_kg = 70
    mock_profil.objectif_principal = "Équilibre"
    mock_profil.niveau_activite = "Sédentaire"
    mock_profil.restrictions_alimentaires = "Aucune"

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_profil
    mock_db.execute.return_value = mock_result

    llm_expected_dict = {
        "statut_motivation": "Excellent profil stable !",
        "analyse_macros": "Vos calories sont parfaitement maîtrisées.",
        "recommandation_repas": "Un filet de saumon avec du riz complet.",
        "alerte_eau": "Pensez à boire votre dernier verre d'eau.",
    }
    mock_llm.return_value = llm_expected_dict

    advice = await generate_nutritional_advice(user_id=42, db_sql=mock_db)

    mock_llm.assert_called_once()
    assert advice["statut_motivation"] == "Excellent profil stable !"
    assert "saumon" in advice["recommandation_repas"]
    assert "debug_error" not in advice
