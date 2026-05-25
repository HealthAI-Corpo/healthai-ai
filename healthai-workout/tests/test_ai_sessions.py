"""Tests des endpoints /ai/* (LLM Ollama et contexte DB mockés)."""

from contextlib import contextmanager
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.database import get_db
from src.main import app

HEADERS = {"X-User-Id": "2"}

CONTEXT = {
    "age": 30,
    "sexe": "Homme",
    "poids_kg": 75,
    "taille_cm": 178,
    "imc": 23.7,
    "niveau_activite": "Modéré",
    "experience_sportive": "Intermédiaire",
    "objectif_principal": "Prise de masse",
    "frequence_entrainement": 3,
    "type_maladie": None,
    "restrictions_alimentaires": None,
    "allergies": None,
}

GEN_LLM = {
    "type_seance": "Musculation",
    "titre_seance": "Haut du corps",
    "duree_minutes": 45,
    "difficulte": "Intermédiaire",
    "objectif": "Prise de masse",
    "conseils_generaux": "Échauffe-toi 10 minutes.",
    "exercices": [
        {
            "nom": "Développé couché",
            "type": "Force",
            "series": 4,
            "repetitions": 10,
            "duree_secondes": 0,
            "repos_secondes": 90,
            "muscles_cibles": "Pectoraux",
        }
    ],
}

EVAL_LLM = {
    "avis_global": "Séances cohérentes avec l'objectif.",
    "note_globale": 4,
    "avis_par_seance": [
        {
            "index": 0,
            "points_positifs": ["Bonne durée"],
            "points_amelioration": ["Varier les exercices"],
            "suggestion": "Ajoute du gainage",
        }
    ],
}

EXPLAIN_LLM = {
    "explications": [
        {
            "nom": "Squat",
            "description": "Flexion des jambes",
            "muscles_cibles": "Quadriceps, fessiers",
            "technique": "Dos droit, descends sous la parallèle.",
            "erreurs_courantes": ["Genoux qui rentrent"],
            "variantes": ["Goblet squat"],
            "conseils_securite": "Garde le dos neutre.",
        }
    ],
}


@pytest.fixture
def mock_db():
    db = MagicMock()
    db.add = MagicMock()
    db.commit = AsyncMock()

    def _refresh(obj):
        obj.id_seance_log = 123
        obj.log_date = datetime(2026, 5, 25, 12, 0, 0)
        obj.statut = "proposee"

    db.refresh = AsyncMock(side_effect=_refresh)
    return db


@pytest.fixture(autouse=True)
def override_db(mock_db):
    async def _get_db():
        yield mock_db

    app.dependency_overrides[get_db] = _get_db
    yield
    app.dependency_overrides.clear()


@contextmanager
def _mock_ai(context=CONTEXT, recent=None, llm=None):
    recent = recent if recent is not None else []
    with (
        patch(
            "src.services.ai_session_service.get_user_context",
            new=AsyncMock(return_value=context),
        ),
        patch(
            "src.services.ai_session_service.get_recent_sessions",
            new=AsyncMock(return_value=recent),
        ),
        patch(
            "src.services.ai_session_service.generate_llm_prediction",
            new=AsyncMock(return_value=llm),
        ),
    ):
        yield


def test_generate_session_no_save(client):
    with _mock_ai(llm=GEN_LLM):
        r = client.post("/ai/generate-session", headers=HEADERS, json={})
    assert r.status_code == 200
    data = r.json()
    assert data["titre_seance"] == "Haut du corps"
    assert data["id_seance_log"] is None  # pas de sauvegarde par défaut
    assert len(data["exercices"]) == 1


def test_generate_session_with_save(client, mock_db):
    with _mock_ai(llm=GEN_LLM):
        r = client.post("/ai/generate-session?sauvegarder=true", headers=HEADERS, json={})
    assert r.status_code == 200
    data = r.json()
    assert data["id_seance_log"] == 123
    assert data["statut"] == "proposee"
    mock_db.add.assert_called_once()
    mock_db.commit.assert_awaited_once()


def test_generate_session_user_not_found(client):
    with _mock_ai(context=None, llm=GEN_LLM):
        r = client.post("/ai/generate-session", headers=HEADERS, json={})
    assert r.status_code == 404


def test_generate_session_missing_header(client):
    r = client.post("/ai/generate-session", json={})
    assert r.status_code == 422


def test_generate_session_bad_llm_output(client):
    with _mock_ai(llm={"champ": "inattendu"}):
        r = client.post("/ai/generate-session", headers=HEADERS, json={})
    assert r.status_code == 502


def _seance_row(id_seance_log, id_utilisateur=2, statut="terminee"):
    s = MagicMock()
    s.id_seance_log = id_seance_log
    s.id_utilisateur = id_utilisateur
    s.type_seance = "Cardio"
    s.duree_minutes = 45
    s.exercices = None
    s.bpm_moyen = 140
    s.statut = statut
    return s


def _result_all(rows):
    r = MagicMock()
    scalars = MagicMock()
    scalars.all.return_value = rows
    r.scalars.return_value = scalars
    return r


def test_evaluate_sessions_by_ids(client, mock_db):
    mock_db.execute = AsyncMock(return_value=_result_all([_seance_row(1)]))
    with _mock_ai(llm=EVAL_LLM):
        r = client.post("/ai/evaluate-sessions", headers=HEADERS, json={"ids_seances": [1]})
    assert r.status_code == 200
    data = r.json()
    assert data["note_globale"] == 4
    assert data["avis_par_seance"][0]["index"] == 0


def test_evaluate_sessions_id_not_found(client, mock_db):
    mock_db.execute = AsyncMock(return_value=_result_all([]))  # aucun id trouvé
    with _mock_ai(llm=EVAL_LLM):
        r = client.post("/ai/evaluate-sessions", headers=HEADERS, json={"ids_seances": [999]})
    assert r.status_code == 404


def test_evaluate_sessions_forbidden(client, mock_db):
    # séance appartenant à un autre utilisateur
    mock_db.execute = AsyncMock(return_value=_result_all([_seance_row(1, id_utilisateur=99)]))
    with _mock_ai(llm=EVAL_LLM):
        r = client.post("/ai/evaluate-sessions", headers=HEADERS, json={"ids_seances": [1]})
    assert r.status_code == 403


def test_evaluate_my_recent_sessions(client, mock_db):
    mock_db.execute = AsyncMock(
        side_effect=[
            _result_all([_seance_row(1, statut="terminee")]),
            _result_all([_seance_row(2, statut="prevue")]),
        ]
    )
    with _mock_ai(llm=EVAL_LLM):
        r = client.get("/ai/evaluate-my-recent-sessions", headers=HEADERS)
    assert r.status_code == 200
    assert r.json()["note_globale"] == 4


def test_evaluate_my_recent_sessions_empty(client, mock_db):
    # aucune séance terminée ni prévue -> 404 (avant tout appel LLM)
    mock_db.execute = AsyncMock(side_effect=[_result_all([]), _result_all([])])
    r = client.get("/ai/evaluate-my-recent-sessions", headers=HEADERS)
    assert r.status_code == 404


def test_explain_exercises(client):
    payload = {"exercices": [{"nom": "Squat"}]}
    with _mock_ai(llm=EXPLAIN_LLM):
        r = client.post("/ai/explain-exercises", headers=HEADERS, json=payload)
    assert r.status_code == 200
    assert r.json()["explications"][0]["nom"] == "Squat"
