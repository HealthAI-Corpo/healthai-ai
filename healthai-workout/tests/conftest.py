"""
Fixtures de test pour healthai-workout.

Les tests unitaires utilisent TestClient sans context manager — la lifespan FastAPI
(chargement modèle ML + connexion MongoDB) n'est donc PAS déclenchée.
Ce conftest.py fournit cependant un mock de CalorieService dans app.state
pour couvrir les tests d'endpoints qui l'utilisent via Depends.
"""

from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from src.main import app
from src.services.calorie_service import CalorieService

_METADATA = {
    "features_cols_order": [
        "imc",
        "age",
        "sexe",
        "bpm_max",
        "bpm_moyen",
        "bpm_repos",
        "duree_seance_minutes",
        "type_sport",
        "pourcentage_gras",
        "consommation_eau_ml",
        "niveau_experience",
    ],
    "encoders": {
        "sexe": {"M": 0, "m": 0, "male": 0, "F": 1, "f": 1, "female": 1},
        "type_sport": {"Cardio": 0, "HIIT": 0, "Strength": 1, "Yoga": 1},
    },
    "scaler_stats": {
        feat: {"mean": 0.0, "std": 1.0}
        for feat in [
            "imc",
            "age",
            "sexe",
            "bpm_max",
            "bpm_moyen",
            "bpm_repos",
            "duree_seance_minutes",
            "type_sport",
            "pourcentage_gras",
            "consommation_eau_ml",
            "niveau_experience",
        ]
    },
    "n_features": 11,
}


@pytest.fixture(scope="session", autouse=True)
def mock_calorie_service():
    """Injecte un CalorieService mocké dans app.state pour la session de tests."""
    mock_model = MagicMock()
    mock_model.predict.return_value = [450.0]

    mock_scaler = MagicMock()
    mock_scaler.transform.return_value = [[0.1] * 11]

    app.state.calorie_service = CalorieService(mock_model, mock_scaler, _METADATA)
    yield
    # Nettoyage minimal — evite les fuites entre sessions pytest
    if hasattr(app.state, "calorie_service"):
        del app.state.calorie_service


@pytest.fixture
def client():
    """TestClient sans context manager : la lifespan (modèle réel, Mongo) n'est pas déclenchée."""
    return TestClient(app)
