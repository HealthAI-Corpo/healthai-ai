"""
Entraînement du moteur hybride de recommandation sportive — RecoIA_1_0_0.

Labels dérivés heuristiquement depuis le dataset biométrique :
  - type_seance  : cardio / force / mixte / mobilité  (depuis type_sport)
  - intensite    : faible / modérée / élevée           (depuis fréquence cardiaque de réserve)
  - muscle_*     : 6 colonnes binaires                 (depuis type_sport, mapping anatomique)

Justification du mapping : en l'absence de logs musculaires explicites dans le dataset,
le type de sport est le meilleur proxy disponible. Axe d'amélioration documenté : ajouter
le tracking musculaire explicite dans log_seance pour un entraînement supervisé réel.

Usage :
    cd healthai-workout
    uv run python scripts/train_recommendation_model.py
"""

import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import classification_report
from sklearn.model_selection import cross_val_score, train_test_split
from sklearn.multioutput import MultiOutputClassifier
from sklearn.preprocessing import LabelEncoder

BASE_DIR = Path(__file__).parent.parent
TRAINING_DATA_DIR = BASE_DIR / "models" / "CaloriesIA_1_0_0" / "training_data"
MODEL_DIR = BASE_DIR / "models" / "RecoIA_1_0_0"

MUSCLES = ["chest", "back", "legs", "shoulders", "core", "arms"]

MUSCLE_MAP: dict[str, list[str]] = {
    "Strength": ["chest", "back", "shoulders", "arms"],
    "Cardio": ["legs", "core"],
    "HIIT": ["legs", "core", "arms"],
    "Yoga": ["core"],
}

TYPE_MAP: dict[str, str] = {
    "Cardio": "cardio",
    "HIIT": "mixte",
    "Strength": "force",
    "Yoga": "mobilité",
}


def engineer_features_and_labels(
    df: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, LabelEncoder, LabelEncoder]:
    df = df.copy()
    df["imc"] = df["poids_kg"] / (df["taille_cm"] / 100) ** 2

    X = df[["age", "imc", "bpm_repos", "niveau_experience", "frequence_sport_jour_semaine"]].copy()

    # Label 1 — type_seance
    df["type_seance"] = df["type_sport"].map(TYPE_MAP)
    le_type = LabelEncoder()
    y_type = pd.Series(le_type.fit_transform(df["type_seance"]), name="type_seance")

    # Label 2 — intensité (fréquence cardiaque de réserve = Karvonen)
    hrr = (df["bpm_moyen"] - df["bpm_repos"]) / (df["bpm_max"] - df["bpm_repos"]).replace(0, 1)
    intensite_cat = pd.cut(
        hrr.clip(0, 1),
        bins=[-np.inf, 0.50, 0.69, np.inf],
        labels=["faible", "modérée", "élevée"],
    )
    le_int = LabelEncoder()
    y_intensite = pd.Series(le_int.fit_transform(intensite_cat.astype(str)), name="intensite")

    # Labels 3–8 — groupes musculaires (multi-label binaire)
    for muscle in MUSCLES:
        df[f"muscle_{muscle}"] = df["type_sport"].apply(
            lambda t: 1 if muscle in MUSCLE_MAP.get(t, []) else 0
        )
    y_muscles = df[[f"muscle_{m}" for m in MUSCLES]]

    y = pd.concat([y_type, y_intensite, y_muscles], axis=1)
    return X, y, le_type, le_int


def train_and_save() -> None:
    print("Chargement du dataset brut...")
    csv_files = sorted(TRAINING_DATA_DIR.glob("Dataset_*.csv"))
    if not csv_files:
        raise FileNotFoundError(f"Aucun Dataset_*.csv trouvé dans {TRAINING_DATA_DIR}")
    df = pd.read_csv(csv_files[-1])
    print(f"  {len(df)} lignes chargées depuis {csv_files[-1].name}")

    X, y, le_type, le_int = engineer_features_and_labels(df)
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    print(f"  Train: {len(X_train)} | Test: {len(X_test)}")

    clf = RandomForestClassifier(n_estimators=100, max_depth=8, random_state=42, n_jobs=-1)
    model = MultiOutputClassifier(clf)
    model.fit(X_train, y_train)

    y_pred = model.predict(X_test)
    metrics: dict = {}

    # Métriques type_seance
    type_names = list(le_type.classes_)
    report_type = classification_report(
        y_test["type_seance"], y_pred[:, 0], target_names=type_names, output_dict=True
    )
    metrics["type_seance"] = {k: v for k, v in report_type.items() if k != "accuracy"}

    # Métriques intensité
    int_names = list(le_int.classes_)
    report_int = classification_report(
        y_test["intensite"], y_pred[:, 1], target_names=int_names, output_dict=True
    )
    metrics["intensite"] = {k: v for k, v in report_int.items() if k != "accuracy"}

    # Métriques groupes musculaires (multi-label)
    muscles_true = y_test[[f"muscle_{m}" for m in MUSCLES]].values
    muscles_pred = y_pred[:, 2:]
    for i, muscle in enumerate(MUSCLES):
        report_m = classification_report(
            muscles_true[:, i], muscles_pred[:, i], output_dict=True, zero_division=0
        )
        metrics[f"muscle_{muscle}"] = report_m

    # Cross-validation 5-fold sur type_seance (label principal, single-output)
    cv_model = RandomForestClassifier(n_estimators=100, max_depth=8, random_state=42, n_jobs=-1)
    cv_scores = cross_val_score(cv_model, X, y["type_seance"], cv=5, scoring="f1_macro")
    metrics["cross_validation"] = {
        "target": "type_seance",
        "scoring": "f1_macro",
        "cv_scores": cv_scores.tolist(),
        "mean": float(cv_scores.mean()),
        "std": float(cv_scores.std()),
    }

    f1_type = report_type["macro avg"]["f1-score"]
    f1_int = report_int["macro avg"]["f1-score"]
    print(f"\n  CV F1 macro type_seance (5-fold) : {cv_scores.mean():.3f} ± {cv_scores.std():.3f}")
    print(f"  F1 macro type_seance : {f1_type:.3f}")
    print(f"  F1 macro intensite   : {f1_int:.3f}")

    # Sauvegarde
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, MODEL_DIR / "model.pkl")
    joblib.dump(le_type, MODEL_DIR / "le_type.pkl")
    joblib.dump(le_int, MODEL_DIR / "le_intensite.pkl")

    with open(MODEL_DIR / "metrics.json", "w") as f:
        json.dump(metrics, f, indent=2, ensure_ascii=False)

    metadata = {
        "features": list(X.columns),
        "labels": list(y.columns),
        "type_seance_classes": list(le_type.classes_),
        "intensite_classes": list(le_int.classes_),
        "muscles": MUSCLES,
        "muscle_map": MUSCLE_MAP,
        "type_map": TYPE_MAP,
        "n_samples_train": len(X_train),
        "n_samples_test": len(X_test),
        "f1_macro_type_seance": round(f1_type, 4),
        "f1_macro_intensite": round(f1_int, 4),
        "cv_f1_macro_mean": round(float(cv_scores.mean()), 4),
        "cv_f1_macro_std": round(float(cv_scores.std()), 4),
    }
    with open(MODEL_DIR / "metadata.json", "w") as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)

    print(f"\nModèles sauvegardés dans {MODEL_DIR}")
    print("Entraînement terminé.")


if __name__ == "__main__":
    train_and_save()
