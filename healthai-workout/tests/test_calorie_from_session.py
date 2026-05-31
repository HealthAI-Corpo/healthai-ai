"""Tests de l'endpoint /calorie-estimation/predict-from-session (DB PostgreSQL mockée).

La séance ne fournit que son id ; le service reconstruit les features depuis la base :
log_seance (bpm_max, consommation_eau_ml, ...), log_sante (bpm_repos, % gras),
profil_sante + utilisateur. niveau_experience reste imputé.
"""

from datetime import date
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.database import get_db
from src.main import app


def _result(scalar=None, first=None):
    """Mocke le retour de db.execute(...) : .scalar_one_or_none() et .scalars().first()."""
    r = MagicMock()
    r.scalar_one_or_none.return_value = scalar
    scalars = MagicMock()
    scalars.first.return_value = first
    r.scalars.return_value = scalars
    return r


def _make_seance(id_utilisateur=1):
    s = MagicMock()
    s.id_seance_log = 1
    s.id_utilisateur = id_utilisateur
    s.calorie_brulee = None
    s.bpm_moyen = 140
    s.bpm_max = 180
    s.consommation_eau_ml = 500
    s.duree_minutes = 45
    s.type_seance = "Cardio"
    return s


def _make_db(results):
    db = MagicMock()
    db.commit = AsyncMock()
    db.execute = AsyncMock(side_effect=results)
    return db


def _override_db(db):
    async def _get_db():
        yield db

    app.dependency_overrides[get_db] = _get_db


@pytest.fixture(autouse=True)
def _clear_overrides():
    yield
    app.dependency_overrides.clear()


def test_predict_from_session_success(client):
    seance = _make_seance()
    utilisateur = MagicMock(date_de_naissance=date(1994, 5, 20), genre="Homme")
    profil = MagicMock(imc=23.5, poids_kg=75, taille_cm=178)
    log_sante = MagicMock(bpm_repos=60, pourcentage_gras=18)
    _override_db(
        _make_db(
            [
                _result(scalar=seance),
                _result(scalar=utilisateur),
                _result(scalar=profil),
                _result(first=log_sante),
            ]
        )
    )

    r = client.post(
        "/calorie-estimation/predict-from-session",
        headers={"X-User-Id": "1"},
        json={"id_seance": 1},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["id_seance"] == 1
    assert data["calories_estimees"] == 450.0
    assert data["calorie_brulee_avant"] is None
    # le champ niveau_experience non disponible doit être imputé
    assert "niveau_experience" in data["champs_utilises"]["imputes"]
    # la séance a bien été mise à jour en base
    assert seance.calorie_brulee == 450.0


def test_predict_from_session_not_found(client):
    _override_db(_make_db([_result(scalar=None)]))
    r = client.post(
        "/calorie-estimation/predict-from-session",
        headers={"X-User-Id": "1"},
        json={"id_seance": 999},
    )
    assert r.status_code == 404


def test_predict_from_session_missing_header(client):
    """Sans X-User-Id (devrait être injecté par la gateway), on renvoie 422."""
    r = client.post("/calorie-estimation/predict-from-session", json={"id_seance": 1})
    assert r.status_code == 422


def test_predict_from_session_forbidden(client):
    # Séance appartenant à un autre utilisateur
    _override_db(_make_db([_result(scalar=_make_seance(id_utilisateur=2))]))
    r = client.post(
        "/calorie-estimation/predict-from-session",
        headers={"X-User-Id": "1"},
        json={"id_seance": 1},
    )
    assert r.status_code == 403
