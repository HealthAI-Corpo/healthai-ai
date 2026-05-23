"""
Module d'entraînement des modèles de machine learning
Responsable de l'entraînement de Random Forest et Gradient Boosting
"""

import logging
import time
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
import pandas as pd

logger = logging.getLogger(__name__)


class ModelTrainingError(Exception):
    """Exception levée lors de l'entraînement des modèles"""
    pass


# ============================================================================
# RANDOM FOREST REGRESSOR
# ============================================================================

def train_random_forest(
    X_train: pd.DataFrame,
    y_train: pd.Series,
    params: dict = None
) -> dict:
    """
    Entraîne un modèle Random Forest Regressor.

    Args:
        X_train: Features d'entraînement (DataFrame)
        y_train: Target d'entraînement (Series)
        params: Dictionnaire de paramètres RF (optionnel)
                Si None, utilise les valeurs par défaut

    Returns:
        dict: Contenant:
            - "model": Modèle RandomForestRegressor entraîné
            - "params": Paramètres utilisés pour l'entraînement
            - "training_time_seconds": Temps d'entraînement en secondes
            - "n_features": Nombre de features utilisées
            - "n_samples_train": Nombre d'échantillons d'entraînement

    Raises:
        ModelTrainingError: Erreur lors de l'entraînement
    """
    logger.info("🌲 Entraînement du modèle Random Forest...")

    try:
        # Valider les inputs
        if X_train.empty or len(y_train) == 0:
            raise ModelTrainingError("X_train ou y_train est vide")

        if len(X_train) != len(y_train):
            raise ModelTrainingError(
                f"Tailles incompatibles: X_train ({len(X_train)}) != y_train ({len(y_train)})"
            )

        # Utiliser les paramètres fournis ou défaut
        if params is None:
            params = {
                "n_estimators": 100,
                "max_depth": 15,
                "min_samples_split": 5,
                "min_samples_leaf": 2,
                "random_state": 42,
                "n_jobs": -1,
            }

        logger.info(f"  Paramètres utilisés:")
        for key, value in params.items():
            logger.info(f"    {key}: {value}")

        # Entraînement
        start_time = time.time()
        
        model = RandomForestRegressor(**params)
        model.fit(X_train, y_train)
        
        training_time = time.time() - start_time

        logger.info(f"✅ Random Forest entraîné en {training_time:.2f}s")
        logger.info(f"  Nombre d'arbres: {model.n_estimators}")
        logger.info(f"  Features utilisées: {model.n_features_in_}")
        logger.info(f"  Échantillons d'entraînement: {len(X_train)}")

        return {
            "model": model,
            "params": params,
            "training_time_seconds": training_time,
            "n_features": model.n_features_in_,
            "n_samples_train": len(X_train),
        }

    except Exception as e:
        error_msg = f"Erreur lors de l'entraînement Random Forest: {type(e).__name__} - {str(e)}"
        logger.error(f"❌ {error_msg}")
        raise ModelTrainingError(error_msg) from e


# ============================================================================
# GRADIENT BOOSTING REGRESSOR
# ============================================================================

def train_gradient_boosting(
    X_train: pd.DataFrame,
    y_train: pd.Series,
    params: dict = None
) -> dict:
    """
    Entraîne un modèle Gradient Boosting Regressor.

    Args:
        X_train: Features d'entraînement (DataFrame)
        y_train: Target d'entraînement (Series)
        params: Dictionnaire de paramètres GB (optionnel)
                Si None, utilise les valeurs par défaut

    Returns:
        dict: Contenant:
            - "model": Modèle GradientBoostingRegressor entraîné
            - "params": Paramètres utilisés pour l'entraînement
            - "training_time_seconds": Temps d'entraînement en secondes
            - "n_features": Nombre de features utilisées
            - "n_samples_train": Nombre d'échantillons d'entraînement

    Raises:
        ModelTrainingError: Erreur lors de l'entraînement
    """
    logger.info("🚀 Entraînement du modèle Gradient Boosting...")

    try:
        # Valider les inputs
        if X_train.empty or len(y_train) == 0:
            raise ModelTrainingError("X_train ou y_train est vide")

        if len(X_train) != len(y_train):
            raise ModelTrainingError(
                f"Tailles incompatibles: X_train ({len(X_train)}) != y_train ({len(y_train)})"
            )

        # Utiliser les paramètres fournis ou défaut
        if params is None:
            params = {
                "n_estimators": 100,
                "learning_rate": 0.1,
                "max_depth": 5,
                "min_samples_split": 5,
                "min_samples_leaf": 2,
                "random_state": 42,
            }

        logger.info(f"  Paramètres utilisés:")
        for key, value in params.items():
            logger.info(f"    {key}: {value}")

        # Entraînement
        start_time = time.time()
        
        model = GradientBoostingRegressor(**params)
        model.fit(X_train, y_train)
        
        training_time = time.time() - start_time

        logger.info(f"✅ Gradient Boosting entraîné en {training_time:.2f}s")
        logger.info(f"  Nombre d'estimateurs: {model.n_estimators}")
        logger.info(f"  Learning rate: {params.get('learning_rate', 0.1)}")
        logger.info(f"  Features utilisées: {model.n_features_in_}")
        logger.info(f"  Échantillons d'entraînement: {len(X_train)}")

        return {
            "model": model,
            "params": params,
            "training_time_seconds": training_time,
            "n_features": model.n_features_in_,
            "n_samples_train": len(X_train),
        }

    except Exception as e:
        error_msg = f"Erreur lors de l'entraînement Gradient Boosting: {type(e).__name__} - {str(e)}"
        logger.error(f"❌ {error_msg}")
        raise ModelTrainingError(error_msg) from e
