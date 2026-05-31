"""
Script de ré-entraînement du modèle CaloriesIA_1_0_0.

Régénère les fichiers model.pkl et scaler.pkl manquants (non versionnés) à partir
des données committées dans models/CaloriesIA_1_0_0/training_data/.

⚠️ IMPORTANT — train_X.csv / test_X.csv sont DÉJÀ STANDARDISÉS (moyenne 0, std 1).
Il ne faut donc PAS re-fitter un StandardScaler dessus : cela produirait un scaler
dégénéré (≈ identité) qui casserait l'inférence (CalorieService applique le scaler
à des features BRUTES). Les vraies statistiques du scaler (calculées sur les données
brutes par le pipeline offline) sont stockées dans transformation_metadata.json
(`scaler_stats`) — on reconstruit le scaler à partir de ces stats, et on entraîne
le modèle directement sur train_X (déjà dans l'espace standardisé).

Usage :
    cd healthai-workout
    uv run python scripts/train_calorie_model.py
"""

import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.preprocessing import StandardScaler

BASE_DIR = Path(__file__).parent.parent
MODEL_DIR = BASE_DIR / "models" / "CaloriesIA_1_0_0"
TRAINING_DATA_DIR = MODEL_DIR / "training_data"
METADATA_PATH = MODEL_DIR / "transformation_metadata.json"


def load_training_data():
    train_X = pd.read_csv(TRAINING_DATA_DIR / "train_X.csv")
    train_y = pd.read_csv(TRAINING_DATA_DIR / "train_y.csv").squeeze()
    test_X = pd.read_csv(TRAINING_DATA_DIR / "test_X.csv")
    test_y = pd.read_csv(TRAINING_DATA_DIR / "test_y.csv").squeeze()
    return train_X, train_y, test_X, test_y


def build_scaler_from_metadata(metadata: dict) -> StandardScaler:
    """Reconstruit le StandardScaler d'inférence depuis les `scaler_stats` committés.

    Ces stats (mean/std par feature) ont été calculées sur les données BRUTES par
    le pipeline offline. On les réinjecte dans un StandardScaler sans le fitter,
    pour que `scaler.transform()` standardise correctement les features brutes
    reçues à l'inférence. L'ordre suit `features_cols_order`.
    """
    features = metadata["features_cols_order"]
    stats = metadata["scaler_stats"]
    scaler = StandardScaler()
    scaler.mean_ = np.array([stats[f]["mean"] for f in features], dtype=float)
    scaler.scale_ = np.array([stats[f]["std"] for f in features], dtype=float)
    scaler.var_ = scaler.scale_**2
    scaler.n_features_in_ = len(features)
    return scaler


def train_and_save():
    print("Chargement des données d'entraînement (déjà standardisées)...")
    train_X, train_y, test_X, test_y = load_training_data()
    print(f"  Train: {len(train_X)} samples | Test: {len(test_X)} samples")

    with open(METADATA_PATH, encoding="utf-8") as f:
        metadata = json.load(f)

    # Scaler d'inférence : reconstruit depuis les stats brutes committées.
    # (NE PAS re-fitter sur train_X qui est déjà scalé — cf. docstring du module.)
    print("Reconstruction du StandardScaler depuis scaler_stats (données brutes)...")
    scaler = build_scaler_from_metadata(metadata)

    # Modèle Random Forest (paramètres du training_log.md), entraîné directement
    # sur train_X qui est déjà dans l'espace standardisé attendu par le modèle.
    print("Entraînement du RandomForestRegressor (n_estimators=150, max_depth=12)...")
    model = RandomForestRegressor(
        n_estimators=150,
        max_depth=12,
        min_samples_split=10,
        min_samples_leaf=4,
        random_state=42,
        n_jobs=-1,
    )
    model.fit(train_X, train_y)

    # Métriques (test_X est déjà standardisé comme train_X)
    predictions = model.predict(test_X)
    mae = float(np.mean(np.abs(predictions - test_y)))
    rmse = float(np.sqrt(np.mean((predictions - test_y) ** 2)))
    ss_res = np.sum((test_y - predictions) ** 2)
    ss_tot = np.sum((test_y - np.mean(test_y)) ** 2)
    r2 = 1 - ss_res / ss_tot if ss_tot != 0 else 0.0
    print(f"  R²={r2:.4f}  MAE={mae:.2f}  RMSE={rmse:.2f}")

    # Sauvegarde — on ne touche PAS à transformation_metadata.json (source de vérité
    # des scaler_stats : ne jamais l'écraser avec des stats re-fittées).
    rf_dir = MODEL_DIR / "random_forest"
    rf_dir.mkdir(parents=True, exist_ok=True)

    model_path = rf_dir / "model.pkl"
    joblib.dump(model, model_path)
    print(f"  Modèle sauvegardé : {model_path}")

    scaler_path = MODEL_DIR / "scaler.pkl"
    joblib.dump(scaler, scaler_path)
    print(f"  Scaler sauvegardé : {scaler_path}")

    print("\nRé-entraînement terminé. Le service peut maintenant démarrer.")


if __name__ == "__main__":
    train_and_save()
