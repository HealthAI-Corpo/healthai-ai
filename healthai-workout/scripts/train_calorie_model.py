"""
Script de ré-entraînement du modèle CaloriesIA_1_0_0.

Utilise les données déjà présentes dans models/CaloriesIA_1_0_0/training_data/
pour régénérer les fichiers model.pkl et scaler.pkl manquants (non versionnés).

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


def train_and_save():
    print("Chargement des données d'entraînement...")
    train_X, train_y, test_X, test_y = load_training_data()
    print(f"  Train: {len(train_X)} samples | Test: {len(test_X)} samples")

    # Scaler — ré-entraîné sur les mêmes données que le run original
    print("Entraînement du StandardScaler...")
    scaler = StandardScaler()
    train_X_scaled = scaler.fit_transform(train_X)
    test_X_scaled = scaler.transform(test_X)

    # Modèle Random Forest (paramètres du training_log.md)
    print("Entraînement du RandomForestRegressor (n_estimators=150, max_depth=12)...")
    model = RandomForestRegressor(
        n_estimators=150,
        max_depth=12,
        min_samples_split=10,
        min_samples_leaf=4,
        random_state=42,
        n_jobs=-1,
    )
    model.fit(train_X_scaled, train_y)

    # Métriques
    predictions = model.predict(test_X_scaled)
    mae = float(np.mean(np.abs(predictions - test_y)))
    rmse = float(np.sqrt(np.mean((predictions - test_y) ** 2)))
    ss_res = np.sum((test_y - predictions) ** 2)
    ss_tot = np.sum((test_y - np.mean(test_y)) ** 2)
    r2 = 1 - ss_res / ss_tot if ss_tot != 0 else 0.0
    print(f"  R²={r2:.4f}  MAE={mae:.2f}  RMSE={rmse:.2f}")

    # Sauvegarde
    rf_dir = MODEL_DIR / "random_forest"
    rf_dir.mkdir(parents=True, exist_ok=True)

    model_path = rf_dir / "model.pkl"
    joblib.dump(model, model_path)
    print(f"  Modèle sauvegardé : {model_path}")

    scaler_path = MODEL_DIR / "scaler.pkl"
    joblib.dump(scaler, scaler_path)
    print(f"  Scaler sauvegardé : {scaler_path}")

    # Mise à jour des stats du scaler dans transformation_metadata.json
    with open(METADATA_PATH, encoding="utf-8") as f:
        metadata = json.load(f)

    features = metadata["features_cols_order"]
    metadata["scaler_stats"] = {
        col: {"mean": float(scaler.mean_[i]), "std": float(scaler.scale_[i])}
        for i, col in enumerate(features)
    }

    with open(METADATA_PATH, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)
    print(f"  Métadonnées mises à jour : {METADATA_PATH}")

    print("\nRé-entraînement terminé. Le service peut maintenant démarrer.")


if __name__ == "__main__":
    train_and_save()
