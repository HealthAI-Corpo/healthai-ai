"""
Module d'évaluation des modèles
Responsable du calcul des métriques et de la comparaison des performances
"""

import logging
import numpy as np
import pandas as pd
from sklearn.metrics import (
    mean_absolute_error,
    mean_squared_error,
    r2_score,
    median_absolute_error
)

logger = logging.getLogger(__name__)


class EvaluationError(Exception):
    """Exception levée lors de l'évaluation des modèles"""
    pass


# ============================================================================
# 1. EVALUATION D'UN SEUL MODELE
# ============================================================================

def evaluate_model(model, X_test: pd.DataFrame, y_test: pd.Series) -> dict:
    """
    Évalue un modèle entraîné sur l'ensemble de test.
    Calcule toutes les métriques et l'importance des features.

    Args:
        model: Modèle sklearn entraîné (RandomForest ou GradientBoosting)
        X_test: Features de test (DataFrame)
        y_test: Target de test (Series)

    Returns:
        dict: Contenant:
            - "predictions": Prédictions sur X_test (array)
            - "mae": Mean Absolute Error
            - "mse": Mean Squared Error
            - "rmse": Root Mean Squared Error
            - "r2": Coefficient de détermination (R²)
            - "mape": Mean Absolute Percentage Error (%)
            - "median_absolute_error": Median Absolute Error
            - "feature_importance": Dict {feature_name: importance_score}
            - "n_features": Nombre de features
            - "n_samples_test": Nombre d'échantillons test

    Raises:
        EvaluationError: Erreur lors de l'évaluation
    """
    try:
        # Prédictions
        y_pred = model.predict(X_test)

        # MAE
        mae = mean_absolute_error(y_test, y_pred)

        # MSE et RMSE
        mse = mean_squared_error(y_test, y_pred)
        rmse = np.sqrt(mse)

        # R²
        r2 = r2_score(y_test, y_pred)

        # MAPE (avec gestion de division par zéro)
        try:
            mape = np.mean(np.abs((y_test - y_pred) / y_test)) * 100
        except Exception as e:
            error_msg = (
                f"Erreur lors du calcul MAPE : {type(e).__name__} - {str(e)}\n"
                f"Vérifier que y_test ne contient pas de 0"
            )
            logger.error(f"❌ {error_msg}")
            raise EvaluationError(error_msg) from e

        # Median Absolute Error
        median_ae = median_absolute_error(y_test, y_pred)

        # Feature Importance
        if hasattr(model, 'feature_importances_'):
            feature_names = X_test.columns.tolist()
            feature_importance = dict(
                zip(feature_names, model.feature_importances_)
            )
            # Trier par importance décroissante
            feature_importance = dict(
                sorted(feature_importance.items(), key=lambda x: x[1], reverse=True)
            )
        else:
            feature_importance = {}

        return {
            "predictions": y_pred,
            "mae": mae,
            "mse": mse,
            "rmse": rmse,
            "r2": r2,
            "mape": mape,
            "median_absolute_error": median_ae,
            "feature_importance": feature_importance,
            "n_features": X_test.shape[1],
            "n_samples_test": len(X_test),
        }

    except EvaluationError:
        raise
    except Exception as e:
        error_msg = f"Erreur lors de l'évaluation du modèle: {type(e).__name__} - {str(e)}"
        logger.error(f"❌ {error_msg}")
        raise EvaluationError(error_msg) from e


# ============================================================================
# 2. EVALUATION DE LA QUALITE DES METRIQUES (BON/MOYEN/MAUVAIS)
# ============================================================================

def evaluate_metrics(metrics_dict: dict, thresholds: dict) -> dict:
    """
    Évalue si les métriques sont bon/moyen/mauvais selon les seuils.

    Logique :
    - Métriques où Plus Haut = Meilleur (R²):
      * bon: >= seuil_bon
      * moyen: >= seuil_moyen
      * mauvais: < seuil_moyen
    
    - Métriques où Plus Bas = Meilleur (MAE, RMSE, MSE, MAPE, etc):
      * bon: <= seuil_bon
      * moyen: <= seuil_moyen
      * mauvais: > seuil_moyen

    Args:
        metrics_dict: Dict de métriques (résultat de evaluate_model)
        thresholds: Dict de seuils (de config.METRICS_THRESHOLDS)

    Returns:
        dict: {
            "quality": {
                "mae": "bon",
                "r2": "moyen",
                ...
            },
            "metrics": metrics_dict (enrichi)
        }
    """
    try:
        quality = {}

        # Métriques où Plus Haut = Meilleur
        higher_is_better = ["r2"]

        # Métriques où Plus Bas = Meilleur
        lower_is_better = ["mae", "mse", "rmse", "mape", "median_absolute_error"]

        for metric_name, threshold_dict in thresholds.items():
            if metric_name not in metrics_dict:
                continue

            value = metrics_dict[metric_name]
            seuil_bon = threshold_dict.get("bon")
            seuil_moyen = threshold_dict.get("moyen")

            if metric_name in higher_is_better:
                # Plus haut = meilleur
                if value >= seuil_bon:
                    quality[metric_name] = "bon"
                elif value >= seuil_moyen:
                    quality[metric_name] = "moyen"
                else:
                    quality[metric_name] = "mauvais"

            elif metric_name in lower_is_better:
                # Plus bas = meilleur
                if value <= seuil_bon:
                    quality[metric_name] = "bon"
                elif value <= seuil_moyen:
                    quality[metric_name] = "moyen"
                else:
                    quality[metric_name] = "mauvais"

        return {
            "quality": quality,
            "metrics": metrics_dict,
        }

    except Exception as e:
        error_msg = f"Erreur lors de l'évaluation de la qualité: {type(e).__name__} - {str(e)}"
        logger.error(f"❌ {error_msg}")
        raise EvaluationError(error_msg) from e


# ============================================================================
# 3. COMPARAISON DES MODELES (RF vs GB vs DummyRegressor)
# ============================================================================

def compare_models(
    rf_metrics: dict,
    gb_metrics: dict,
    baseline_metrics: dict
) -> dict:
    """
    Compare les 3 modèles (RF, GB, Baseline) sur toutes les métriques.
    Génère un classement 1-3 pour chaque métrique.

    Logique de ranking :
    - Pour R² (Plus haut = meilleur): 1 = meilleur (plus haut), 3 = pire (plus bas)
    - Pour MAE, RMSE, etc (Plus bas = meilleur): 1 = meilleur (plus bas), 3 = pire (plus haut)

    Args:
        rf_metrics: Dict de métriques RandomForest
        gb_metrics: Dict de métriques GradientBoosting
        baseline_metrics: Dict de métriques DummyRegressor

    Returns:
        dict: {
            "rankings": {
                "mae": {"random_forest": 1, "gradient_boosting": 2, "baseline": 3, "winner": "random_forest"},
                ...
            },
            "summary": {
                "random_forest": nb_premieres_places,
                "gradient_boosting": nb_premieres_places,
                "baseline": nb_premieres_places,
                "best_overall": "random_forest"
            }
        }
    """
    try:
        rankings = {}
        overall_scores = {
            "random_forest": 0,
            "gradient_boosting": 0,
            "baseline": 0,
        }

        # Métriques où Plus Bas = Meilleur
        lower_is_better = ["mae", "mse", "rmse", "mape", "median_absolute_error"]

        # ---- R² (Plus haut = meilleur) ----
        if "r2" in rf_metrics and "r2" in gb_metrics and "r2" in baseline_metrics:
            r2_values = {
                "random_forest": rf_metrics["r2"],
                "gradient_boosting": gb_metrics["r2"],
                "baseline": baseline_metrics["r2"],
            }
            # Trier par valeur décroissante (plus haut = meilleur = rang 1)
            ranked = sorted(r2_values.items(), key=lambda x: x[1], reverse=True)
            rankings["r2"] = {
                model: rank + 1 for rank, (model, _) in enumerate(ranked)
            }
            rankings["r2"]["winner"] = ranked[0][0]
            overall_scores[ranked[0][0]] += 1  # +1 pour le gagnant

        # ---- Métriques où Plus Bas = Meilleur ----
        for metric in lower_is_better:
            if metric in rf_metrics and metric in gb_metrics and metric in baseline_metrics:
                metric_values = {
                    "random_forest": rf_metrics[metric],
                    "gradient_boosting": gb_metrics[metric],
                    "baseline": baseline_metrics[metric],
                }
                # Trier par valeur croissante (plus bas = meilleur = rang 1)
                ranked = sorted(metric_values.items(), key=lambda x: x[1])
                rankings[metric] = {
                    model: rank + 1 for rank, (model, _) in enumerate(ranked)
                }
                rankings[metric]["winner"] = ranked[0][0]
                overall_scores[ranked[0][0]] += 1  # +1 pour le gagnant

        # Déterminer le meilleur modèle global
        best_overall = max(overall_scores.items(), key=lambda x: x[1])[0]

        return {
            "rankings": rankings,
            "summary": {
                **overall_scores,
                "best_overall": best_overall,
            },
        }

    except Exception as e:
        error_msg = f"Erreur lors de la comparaison des modèles: {type(e).__name__} - {str(e)}"
        logger.error(f"❌ {error_msg}")
        raise EvaluationError(error_msg) from e
