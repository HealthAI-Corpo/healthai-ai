"""
Configuration et constantes du POC - Prédiction Calories Brûlées
"""

import os
from pathlib import Path

# ============================================================================
# CHEMINS
# ============================================================================

# Racine du projet
PROJECT_ROOT = Path(__file__).parent
DATA_DIR = PROJECT_ROOT / "data"
DATA_RAW_DIR = DATA_DIR / "raw"
DATA_MODELS_DIR = DATA_DIR / "models"
LOGS_DIR = PROJECT_ROOT / "logs"
NOTEBOOKS_DIR = PROJECT_ROOT / "notebooks"

# Fichiers de données
CSV_FILE = DATA_RAW_DIR / "dataset_historique_seance_exercice.20260519.csv"

# ============================================================================
# SCHEMA DE DONNEES
# ============================================================================

# Colonnes attendues avec leurs types
SCHEMA = {
    "age": "int64",
    "sexe": "str",  # M, F
    # PHASE 6 MOD: Fusion poids + taille → IMC
    "poids_kg": "float64",  # Transformé en IMC
    "taille_cm": "int64",  # Transformé en IMC
    "bpm_max": "int64",
    "bpm_moyen": "int64",
    "bpm_repos": "int64",
    "duree_seance_minutes": "float64",
    "calories_brulees": "float64",  # TARGET
    "type_sport": "str",  # Texte
    "pourcentage_gras": "float64",
    "consommation_eau_ml": "float64",
    # PHASE 6 MOD: Suppression de frequence_sport_jour_semaine
    # Raison: 1) Importance marginale (4-5%), 2) Redondant avec durée/BPM,
    #         3) Variable de profil utilisateur, pas de séance actuelle
    # "frequence_sport_jour_semaine": "int64",  # REMOVED
    "niveau_experience": "int64",  # 1-5
}

# Colonnes à garder (toutes sauf certaines optionnelles)
FEATURES_COLS = [col for col in SCHEMA.keys() if col != "calories_brulees"]
TARGET_COL = "calories_brulees"

# Colonnes catégoriques à encoder, ici juste pour doc
CATEGORICAL_COLS = {
    "sexe": {
        # Accepter plusieurs variantes
        "M": 0,
        "m": 0,
        "male": 0,
        "Male": 0,
        "F": 1,
        "f": 1,
        "female": 1,
        "Female": 1,
    },
    # Au lieu de one-hot (2 colonnes), une seule colonne: 0=Cardio, 1=Force
    # Cardio: Cardio + HIIT (effort cardio-vasculaire)
    # Force: Strength + Yoga (effort musculaire/flexibilité)
    "type_sport": {
        "Cardio": 0,
        "HIIT": 0,
        "Strength": 1,
        "Yoga": 1,
    },
}

# ============================================================================
# PARAMETRES DE PREPROCESSING
# ============================================================================

# Split train/test
TRAIN_TEST_SPLIT_RATIO = 0.8
RANDOM_STATE = 42

# Normalisation
NORMALIZE_NUMERIC = True  # StandardScaler
SCALING_METHOD = "standard"  # "standard" ou "minmax"

# Valeurs manquantes
DROP_MISSING = True  # True : supprimer les lignes avec NaN
FILL_MISSING = False  # True : remplir avec la moyenne/médiane

# ============================================================================
# PARAMETRES DES MODELES
# ============================================================================

# Random Forest
# PHASE 6 OPTIM: Optimisation des hyperparamètres pour réduire l'overfitting
# Ancien (v1_11): n_est=100, max_depth=15, min_split=5, min_leaf=2
# Nouveau (v1_12+): Plus conservatif pour meilleure généralisation
RF_PARAMS = {
    "n_estimators": 150,  # Augmenté de 100 → 150 (stabilité ensemble)
    "max_depth": 12,  # Réduit de 15 → 12 (moins d'overfitting)
    "min_samples_split": 10,  # Augmenté de 5 → 10 (arbres moins spécialisés)
    "min_samples_leaf": 4,  # Augmenté de 2 → 4 (feuilles plus générales)
    "random_state": RANDOM_STATE,
    "n_jobs": -1,
}

# Gradient Boosting
GB_PARAMS = {
    "n_estimators": 100,
    "learning_rate": 0.1,
    "max_depth": 5,
    "min_samples_split": 5,
    "min_samples_leaf": 2,
    "random_state": RANDOM_STATE,
}

# ============================================================================
# PARAMETRES D'EVALUATION - THRESHOLDS DES METRIQUES
# ============================================================================

# Seuils pour évaluer la qualité d'une métrique (bon/moyen/mauvais)
# Structure: {metrique: {"bon": seuil_bon, "moyen": seuil_moyen}}
# Logique :
#   - Métriques où Plus Haut = Meilleur (R²):
#       bon: >= seuil_bon
#       moyen: >= seuil_moyen
#       mauvais: < seuil_moyen
#
#   - Métriques où Plus Bas = Meilleur (MAE, RMSE, MSE, MAPE, etc):
#       bon: <= seuil_bon
#       moyen: <= seuil_moyen
#       mauvais: > seuil_moyen

METRICS_THRESHOLDS = {
    # R² : Plus haut = meilleur (0 à 1)
    # bon: >= 0.75, moyen: >= 0.60
    "r2": {
        "bon": 0.75,
        "moyen": 0.60,
    },
    # MAE (Mean Absolute Error) : Plus bas = meilleur
    # bon: <= 50, moyen: <= 100 (calories)
    "mae": {
        "bon": 50.0,
        "moyen": 100.0,
    },
    # RMSE (Root Mean Square Error) : Plus bas = meilleur
    # bon: <= 70, moyen: <= 130
    "rmse": {
        "bon": 70.0,
        "moyen": 130.0,
    },
    # MSE (Mean Square Error) : Plus bas = meilleur
    # bon: <= 5000, moyen: <= 17000
    "mse": {
        "bon": 5000.0,
        "moyen": 17000.0,
    },
    # MAPE (Mean Absolute Percentage Error) : Plus bas = meilleur (en %)
    # bon: <= 10%, moyen: <= 20%
    "mape": {
        "bon": 10.0,
        "moyen": 20.0,
    },
    # Median Absolute Error : Plus bas = meilleur
    # bon: <= 40, moyen: <= 80
    "median_absolute_error": {
        "bon": 40.0,
        "moyen": 80.0,
    },
}

# ============================================================================
# PARAMETRES DE SAUVEGARDE
# ============================================================================

# ============================================================================
# PARAMETRES DE SAUVEGARDE ET VERSIONING
# ============================================================================

# Nom du modèle (dossier parent)
MODEL_NAME = "CaloriesPOC"

# Version majeure (définie par l'admin, x s'auto-incrémente)
# Format final : v{VERSION_MAJOR}_x_<timestamp>
# Exemple : v1_1_20260521_143022 (v1 = version_major, 1 = x auto-incrémenté, timestamp = date/heure)
VERSION_MAJOR = "1"
