"""Tests des endpoints /calorie-estimation/* (CalorieService mocké via conftest)."""

# Payload complet et valide (passe _validate_input du service).
VALID = {
    "imc": 23.5,
    "age": 30,
    "sexe": "M",
    "bpm_max": 180,
    "bpm_moyen": 140,
    "bpm_repos": 60,
    "duree_seance_minutes": 45,
    "type_sport": "Cardio",
    "pourcentage_gras": 18.0,
    "consommation_eau_ml": 500,
    "niveau_experience": 3,
}


def test_model_info(client):
    r = client.get("/calorie-estimation/model-info")
    assert r.status_code == 200
    assert r.json()["model_name"] == "CaloriesIA_1_0_0"


def test_metrics(client):
    r = client.get("/calorie-estimation/metrics")
    assert r.status_code == 200
    assert "r2_score" in r.json()


def test_predict_success(client):
    r = client.post("/calorie-estimation/predict", json=VALID)
    assert r.status_code == 200
    assert r.json()["prediction"] == 450.0


def test_predict_invalid_sexe(client):
    r = client.post("/calorie-estimation/predict", json={**VALID, "sexe": "X"})
    assert r.status_code == 422


def test_predict_invalid_bpm_order(client):
    # bpm_repos >= bpm_moyen => rejeté par _validate_input
    r = client.post("/calorie-estimation/predict", json={**VALID, "bpm_repos": 150})
    assert r.status_code == 422


def test_predict_with_defaults_missing_sexe(client):
    # Régression bug A : un champ catégoriel absent (sexe) est imputé en numérique,
    # l'encodage ne doit plus appeler .strip() dessus.
    payload = {k: v for k, v in VALID.items() if k != "sexe"}
    r = client.post("/calorie-estimation/predict-with-defaults", json=payload)
    assert r.status_code == 200
    body = r.json()
    assert body["prediction"] == 450.0
    assert "sexe" in body["imputed_features"]
    assert "sexe" not in body["original_values"]
