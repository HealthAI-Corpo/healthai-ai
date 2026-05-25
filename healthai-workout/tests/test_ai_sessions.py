"""Tests des endpoints /ai/* en mode asynchrone (202 + polling).

Les routes renvoient un job_id ; le travail Ollama tourne en BackgroundTask (exécutée
par TestClient pendant l'appel POST). On interroge ensuite GET /ai/jobs/{id}.
LLM Ollama, contexte DB et store Mongo sont mockés.
"""

from contextlib import contextmanager
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from bson import ObjectId

from src.database import get_db
from src.database_mongo import mongo_db
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


# --- Faux store Mongo + session DG de fond --------------------------------------


class _FakeColl:
    def __init__(self):
        self.docs = {}

    async def insert_one(self, doc):
        _id = ObjectId()
        doc = dict(doc)
        doc["_id"] = _id
        self.docs[str(_id)] = doc
        return MagicMock(inserted_id=_id)

    async def update_one(self, flt, update):
        key = str(flt["_id"])
        if key in self.docs:
            self.docs[key].update(update["$set"])
        return MagicMock()

    async def find_one(self, flt):
        doc = self.docs.get(str(flt["_id"]))
        return dict(doc) if doc else None


class _FakeDB:
    def __init__(self):
        object.__setattr__(self, "_colls", {})

    def __getitem__(self, name):
        return self._colls.setdefault(name, _FakeColl())

    def __getattr__(self, name):  # accès attribut (ex: mongo_db.db.predictions)
        colls = object.__getattribute__(self, "_colls")
        return colls.setdefault(name, _FakeColl())


@pytest.fixture
def mongo_jobs(monkeypatch, mock_db):
    """Rend Mongo disponible (require_mongo OK) et fait pointer la session de fond sur mock_db."""
    monkeypatch.setattr(mongo_db, "db", _FakeDB())

    class _Ctx:
        async def __aenter__(self):
            return mock_db

        async def __aexit__(self, *exc):
            return False

    monkeypatch.setattr("src.services.job_service.AsyncSessionLocal", lambda: _Ctx())


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


def _poll(client, job_id):
    r = client.get(f"/ai/jobs/{job_id}")
    assert r.status_code == 200
    return r.json()


def test_generate_session_no_save(client, mongo_jobs):
    with _mock_ai(llm=GEN_LLM):
        r = client.post("/ai/generate-session", headers=HEADERS, json={})
    assert r.status_code == 202
    job = _poll(client, r.json()["job_id"])
    assert job["status"] == "completed"
    result = job["result"]
    assert result["titre_seance"] == "Haut du corps"
    assert result["id_seance_log"] is None  # pas de sauvegarde par défaut
    assert len(result["exercices"]) == 1


def test_generate_session_with_save(client, mongo_jobs, mock_db):
    with _mock_ai(llm=GEN_LLM):
        r = client.post("/ai/generate-session?sauvegarder=true", headers=HEADERS, json={})
    assert r.status_code == 202
    job = _poll(client, r.json()["job_id"])
    assert job["status"] == "completed"
    assert job["result"]["id_seance_log"] == 123
    assert job["result"]["statut"] == "proposee"
    mock_db.add.assert_called_once()
    mock_db.commit.assert_awaited_once()


def test_generate_session_user_not_found(client, mongo_jobs):
    with _mock_ai(context=None, llm=GEN_LLM):
        r = client.post("/ai/generate-session", headers=HEADERS, json={})
    assert r.status_code == 202
    job = _poll(client, r.json()["job_id"])
    assert job["status"] == "failed"
    assert job["error_code"] == 404


def test_generate_session_missing_header(client, mongo_jobs):
    r = client.post("/ai/generate-session", json={})
    assert r.status_code == 422


def test_generate_session_bad_llm_output(client, mongo_jobs):
    with _mock_ai(llm={"champ": "inattendu"}):
        r = client.post("/ai/generate-session", headers=HEADERS, json={})
    assert r.status_code == 202
    job = _poll(client, r.json()["job_id"])
    assert job["status"] == "failed"
    assert job["error_code"] == 502


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


def test_evaluate_sessions_by_ids(client, mongo_jobs, mock_db):
    mock_db.execute = AsyncMock(return_value=_result_all([_seance_row(1)]))
    with _mock_ai(llm=EVAL_LLM):
        r = client.post("/ai/evaluate-sessions", headers=HEADERS, json={"ids_seances": [1]})
    assert r.status_code == 202
    job = _poll(client, r.json()["job_id"])
    assert job["status"] == "completed"
    assert job["result"]["note_globale"] == 4
    assert job["result"]["avis_par_seance"][0]["index"] == 0


def test_evaluate_sessions_id_not_found(client, mongo_jobs, mock_db):
    mock_db.execute = AsyncMock(return_value=_result_all([]))  # aucun id trouvé
    with _mock_ai(llm=EVAL_LLM):
        r = client.post("/ai/evaluate-sessions", headers=HEADERS, json={"ids_seances": [999]})
    assert r.status_code == 202
    job = _poll(client, r.json()["job_id"])
    assert job["status"] == "failed"
    assert job["error_code"] == 404


def test_evaluate_sessions_forbidden(client, mongo_jobs, mock_db):
    # séance appartenant à un autre utilisateur
    mock_db.execute = AsyncMock(return_value=_result_all([_seance_row(1, id_utilisateur=99)]))
    with _mock_ai(llm=EVAL_LLM):
        r = client.post("/ai/evaluate-sessions", headers=HEADERS, json={"ids_seances": [1]})
    assert r.status_code == 202
    job = _poll(client, r.json()["job_id"])
    assert job["status"] == "failed"
    assert job["error_code"] == 403


def test_evaluate_my_recent_sessions(client, mongo_jobs, mock_db):
    mock_db.execute = AsyncMock(
        side_effect=[
            _result_all([_seance_row(1, statut="terminee")]),
            _result_all([_seance_row(2, statut="prevue")]),
        ]
    )
    with _mock_ai(llm=EVAL_LLM):
        r = client.get("/ai/evaluate-my-recent-sessions", headers=HEADERS)
    assert r.status_code == 202
    job = _poll(client, r.json()["job_id"])
    assert job["status"] == "completed"
    assert job["result"]["note_globale"] == 4


def test_evaluate_my_recent_sessions_empty(client, mongo_jobs, mock_db):
    # aucune séance terminée ni prévue -> job en échec 404
    mock_db.execute = AsyncMock(side_effect=[_result_all([]), _result_all([])])
    with _mock_ai(llm=EVAL_LLM):
        r = client.get("/ai/evaluate-my-recent-sessions", headers=HEADERS)
    assert r.status_code == 202
    job = _poll(client, r.json()["job_id"])
    assert job["status"] == "failed"
    assert job["error_code"] == 404


def test_explain_exercises(client, mongo_jobs):
    payload = {"exercices": [{"nom": "Squat"}]}
    with _mock_ai(llm=EXPLAIN_LLM):
        r = client.post("/ai/explain-exercises", headers=HEADERS, json=payload)
    assert r.status_code == 202
    job = _poll(client, r.json()["job_id"])
    assert job["status"] == "completed"
    assert job["result"]["explications"][0]["nom"] == "Squat"


def test_job_not_found(client, mongo_jobs):
    r = client.get(f"/ai/jobs/{ObjectId()}")
    assert r.status_code == 404


def test_generate_session_mongo_unavailable(client):
    # Sans la fixture mongo_jobs, mongo_db.db est None -> 503
    r = client.post("/ai/generate-session", headers=HEADERS, json={})
    assert r.status_code == 503
