"""
Module de sérialisation et sauvegarde des modèles
Responsable de la sauvegarde complète : modèles, métriques, données, logs, métadonnées
"""

import logging
import json
from pathlib import Path
from datetime import datetime

import joblib
import pandas as pd

from config import TARGET_COL

logger = logging.getLogger(__name__)


class SerializationError(Exception):
    """Exception levée lors de la sérialisation"""

    pass


# ============================================================================
# 1. GESTION DE VERSIONING
# ============================================================================


def get_next_version_dir(
    model_name: str, version_major: str, models_root: Path
) -> tuple:
    """
    Génère le répertoire de la prochaine version.
    Format : v{major}_x_{timestamp}

    Logique :
    - Cherche les dossiers existants pour cette version majeure
    - Auto-incrémente x (v1_1, v1_2, v1_3, etc.)
    - Génère le timestamp actuel

    Args:
        model_name: Nom du modèle (ex: "CaloriesPOC")
        version_major: Version majeure (ex: "1")
        models_root: Racine des modèles (ex: data/models)

    Returns:
        tuple: (version_dir_path, version_string)

    Raises:
        SerializationError: Erreur lors de la génération de la version
    """
    try:
        model_dir = models_root / model_name

        # Trouver le plus haut x pour cette version majeure
        max_x = 0
        if model_dir.exists():
            for d in model_dir.iterdir():
                if d.is_dir() and d.name.startswith(f"v{version_major}_"):
                    try:
                        # Extraire x de v1_2_20260521_143022
                        parts = d.name.split("_")
                        if len(parts) >= 2:
                            x_val = int(parts[1])
                            max_x = max(max_x, x_val)
                    except (ValueError, IndexError):
                        continue

        # Prochaine valeur de x
        next_x = max_x + 1

        # Timestamp
        now = datetime.now()
        timestamp = now.strftime("%Y%m%d_%H%M%S")

        # Version string et chemin
        version_string = f"v{version_major}_{next_x}_{timestamp}"
        version_dir = model_dir / version_string

        logger.info(f"📦 Prochaine version générée : {version_string}")
        return version_dir, version_string

    except Exception as e:
        error_msg = (
            f"Erreur lors de la génération de version: {type(e).__name__} - {str(e)}"
        )
        logger.error(f"❌ {error_msg}")
        raise SerializationError(error_msg) from e


# ============================================================================
# 2. SAUVEGARDE DES MODELES
# ============================================================================


def save_model(model, model_name: str, version_dir: Path, algo_type: str) -> str:
    """
    Sauvegarde un modèle entraîné en .pkl

    Args:
        model: Modèle sklearn entraîné
        model_name: Nom du modèle ("RandomForest" ou "GradientBoosting")
        version_dir: Répertoire de version
        algo_type: Type d'algo ("random_forest" ou "gradient_boosting")

    Returns:
        str: Chemin du fichier modèle sauvegardé

    Raises:
        SerializationError: Erreur lors de la sauvegarde
    """
    try:
        algo_dir = version_dir / algo_type
        algo_dir.mkdir(parents=True, exist_ok=True)

        model_path = algo_dir / "model.pkl"
        joblib.dump(model, model_path)

        logger.info(f"✅ {model_name} sauvegardé: {model_path}")
        return str(model_path)

    except Exception as e:
        error_msg = f"Erreur lors de la sauvegarde du modèle {model_name}: {type(e).__name__} - {str(e)}"
        logger.error(f"❌ {error_msg}")
        raise SerializationError(error_msg) from e


# ============================================================================
# 3. SAUVEGARDE DES METRIQUES
# ============================================================================


def save_metrics(metrics_dict: dict, version_dir: Path, algo_type: str) -> str:
    """
    Sauvegarde les métriques en JSON

    Args:
        metrics_dict: Dict avec les métriques (MAE, R², RMSE, etc.)
        version_dir: Répertoire de version
        algo_type: Type d'algo

    Returns:
        str: Chemin du fichier métriques

    Raises:
        SerializationError: Erreur lors de la sauvegarde
    """
    try:
        algo_dir = version_dir / algo_type
        algo_dir.mkdir(parents=True, exist_ok=True)

        metrics_path = algo_dir / "metrics.json"

        # Supprimer les clés non-sérialisables (predictions, feature_importance dict)
        metrics_to_save = {
            k: v
            for k, v in metrics_dict.items()
            if k not in ["predictions", "feature_importance"]
        }

        with open(metrics_path, "w", encoding="utf-8") as f:
            json.dump(metrics_to_save, f, indent=2)

        logger.info(f"✅ Métriques sauvegardées: {metrics_path}")

        # Sauvegarder feature_importance dans un fichier JSON séparé
        if "feature_importance" in metrics_dict and metrics_dict["feature_importance"]:
            feature_importance_path = algo_dir / "feature_importance.json"
            feature_importance_data = metrics_dict["feature_importance"]

            # Convertir en pourcentages
            total_importance = sum(feature_importance_data.values())
            feature_importance_pct = {
                col: (importance / total_importance * 100)
                if total_importance > 0
                else 0
                for col, importance in feature_importance_data.items()
            }

            with open(feature_importance_path, "w", encoding="utf-8") as f:
                json.dump(feature_importance_pct, f, indent=2)

            logger.info(f"✅ Feature importance sauvegardé: {feature_importance_path}")

        # Sauvegarder les predictions dans un fichier CSV séparé
        if "predictions" in metrics_dict and metrics_dict["predictions"] is not None:
            predictions_path = algo_dir / "predictions.csv"
            predictions_df = pd.DataFrame(
                metrics_dict["predictions"], columns=["prediction"]
            )
            predictions_df.to_csv(predictions_path, index=False)
            logger.info(f"✅ Predictions sauvegardées: {predictions_path}")

        return str(metrics_path)

    except Exception as e:
        error_msg = (
            f"Erreur lors de la sauvegarde des métriques: {type(e).__name__} - {str(e)}"
        )
        logger.error(f"❌ {error_msg}")
        raise SerializationError(error_msg) from e


# ============================================================================
# 4. SAUVEGARDE DES DONNEES D'ENTRAINEMENT
# ============================================================================


def save_training_data(
    X_train: pd.DataFrame,
    X_test: pd.DataFrame,
    y_train: pd.Series,
    y_test: pd.Series,
    df_raw: pd.DataFrame,
    version_dir: Path,
) -> dict:
    """
    Sauvegarde les données d'entraînement normalisées et le CSV original

    Args:
        X_train, X_test, y_train, y_test: Données normalisées/encodées
        df_raw: DataFrame original brut (avant preprocessing)
        version_dir: Répertoire de version

    Returns:
        dict: Chemins des fichiers sauvegardés

    Raises:
        SerializationError: Erreur lors de la sauvegarde
    """
    try:
        data_dir = version_dir / "training_data"
        data_dir.mkdir(parents=True, exist_ok=True)

        paths = {}

        # Sauvegarder les données normalisées
        train_X_path = data_dir / "train_X.csv"
        X_train.to_csv(train_X_path, index=False)
        paths["train_X"] = str(train_X_path)

        test_X_path = data_dir / "test_X.csv"
        X_test.to_csv(test_X_path, index=False)
        paths["test_X"] = str(test_X_path)

        train_y_path = data_dir / "train_y.csv"
        y_train.to_csv(train_y_path, index=False, header=[TARGET_COL])
        paths["train_y"] = str(train_y_path)

        test_y_path = data_dir / "test_y.csv"
        y_test.to_csv(test_y_path, index=False, header=[TARGET_COL])
        paths["test_y"] = str(test_y_path)

        # Sauvegarder le CSV original
        now = datetime.now()
        timestamp = now.strftime("%Y%m%d_%H%M%S")
        raw_csv_name = f"Dataset_{timestamp}.csv"
        raw_csv_path = data_dir / raw_csv_name
        df_raw.to_csv(raw_csv_path, index=False)
        paths["dataset_original"] = str(raw_csv_path)

        logger.info(f"✅ Données d'entraînement sauvegardées: {data_dir}")
        return paths

    except Exception as e:
        error_msg = (
            f"Erreur lors de la sauvegarde des données: {type(e).__name__} - {str(e)}"
        )
        logger.error(f"❌ {error_msg}")
        raise SerializationError(error_msg) from e


# ============================================================================
# 5. SAUVEGARDE DU SCALER
# ============================================================================


def save_scaler(scaler, version_dir: Path) -> str:
    """
    Sauvegarde le StandardScaler en .pkl

    Args:
        scaler: StandardScaler entraîné
        version_dir: Répertoire de version

    Returns:
        str: Chemin du fichier scaler

    Raises:
        SerializationError: Erreur lors de la sauvegarde
    """
    try:
        scaler_path = version_dir / "scaler.pkl"
        joblib.dump(scaler, scaler_path)
        logger.info(f"✅ Scaler sauvegardé: {scaler_path}")
        return str(scaler_path)

    except Exception as e:
        error_msg = (
            f"Erreur lors de la sauvegarde du scaler: {type(e).__name__} - {str(e)}"
        )
        logger.error(f"❌ {error_msg}")
        raise SerializationError(error_msg) from e


# ============================================================================
# 6. SAUVEGARDE DES METADONNEES DE TRANSFORMATION
# ============================================================================


def save_transformation_metadata(
    scaler, encoders: dict, features_cols_final: list, version_dir: Path
) -> str:
    """
    Sauvegarde les métadonnées de transformation (CRITIQUE POUR INFÉRENCE)

    Contient :
    - Encoders (sexe, type_sport)
    - Mean/std du scaler
    - Liste des features dans l'ordre exact

    Args:
        scaler: StandardScaler entraîné
        encoders: Dict avec encoders (sexe, type_sport)
        features_cols_final: Liste des colonnes finales
        version_dir: Répertoire de version

    Returns:
        str: Chemin du fichier métadonnées

    Raises:
        SerializationError: Erreur lors de la sauvegarde
    """
    try:
        metadata_path = version_dir / "transformation_metadata.json"

        # Extraire mean et std du scaler
        scaler_stats = {}
        if scaler and hasattr(scaler, "mean_") and hasattr(scaler, "scale_"):
            for i, col in enumerate(features_cols_final):
                scaler_stats[col] = {
                    "mean": float(scaler.mean_[i]) if i < len(scaler.mean_) else 0.0,
                    "std": float(scaler.scale_[i]) if i < len(scaler.scale_) else 1.0,
                }

        metadata = {
            "encoders": encoders,
            "scaler_stats": scaler_stats,
            "features_cols_order": features_cols_final,
            "n_features": len(features_cols_final),
        }

        with open(metadata_path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2)

        logger.info(f"✅ Métadonnées de transformation sauvegardées: {metadata_path}")
        return str(metadata_path)

    except Exception as e:
        error_msg = f"Erreur lors de la sauvegarde des métadonnées: {type(e).__name__} - {str(e)}"
        logger.error(f"❌ {error_msg}")
        raise SerializationError(error_msg) from e


# ============================================================================
# 7. GENERATION DU LOG D'ENTRAINEMENT
# ============================================================================


def save_training_log(
    version_string: str,
    rf_train_result: dict,
    gb_train_result: dict,
    rf_eval_result: dict,
    gb_eval_result: dict,
    baseline_eval_result: dict,
    comparison_result: dict,
    n_train: int,
    n_test: int,
    version_dir: Path,
) -> str:
    """
    Génère un log d'entraînement complet en Markdown

    Args:
        version_string: String de version (ex: v1_1_20260521_143022)
        rf_train_result: Résultats d'entraînement RF
        gb_train_result: Résultats d'entraînement GB
        rf_eval_result: Résultats d'évaluation RF
        gb_eval_result: Résultats d'évaluation GB
        baseline_eval_result: Résultats d'évaluation baseline
        comparison_result: Résultats de comparaison
        n_train: Nombre d'échantillons train
        n_test: Nombre d'échantillons test
        version_dir: Répertoire de version

    Returns:
        str: Chemin du fichier log

    Raises:
        SerializationError: Erreur lors de la génération
    """
    try:
        log_path = version_dir / "training_log.md"

        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        log_content = f"""# Training Log - {version_string}

**Date d'entraînement** : {now}

---

## 📊 Résumé Général

| Métrique | Valeur |
|----------|--------|
| Version | {version_string} |
| Échantillons Train | {n_train} |
| Échantillons Test | {n_test} |
| Temps RF | {rf_train_result.get("training_time_seconds", "N/A"):.2f}s |
| Temps GB | {gb_train_result.get("training_time_seconds", "N/A"):.2f}s |

---

## 🌲 Random Forest Regressor

### Paramètres
"""

        # Ajouter paramètres RF
        for param, value in rf_train_result.get("params", {}).items():
            log_content += f"- `{param}`: {value}\n"

        log_content += f"""
### Résultats d'Évaluation
| Métrique | Valeur |
|----------|--------|
| R² | {rf_eval_result.get("r2", "N/A"):.4f} |
| MAE | {rf_eval_result.get("mae", "N/A"):.2f} |
| RMSE | {rf_eval_result.get("rmse", "N/A"):.2f} |
| MSE | {rf_eval_result.get("mse", "N/A"):.2f} |
| MAPE (%) | {rf_eval_result.get("mape", "N/A"):.2f} |
| Median AE | {rf_eval_result.get("median_absolute_error", "N/A"):.2f} |

---

## 🚀 Gradient Boosting Regressor

### Paramètres
"""

        # Ajouter paramètres GB
        for param, value in gb_train_result.get("params", {}).items():
            log_content += f"- `{param}`: {value}\n"

        log_content += f"""
### Résultats d'Évaluation
| Métrique | Valeur |
|----------|--------|
| R² | {gb_eval_result.get("r2", "N/A"):.4f} |
| MAE | {gb_eval_result.get("mae", "N/A"):.2f} |
| RMSE | {gb_eval_result.get("rmse", "N/A"):.2f} |
| MSE | {gb_eval_result.get("mse", "N/A"):.2f} |
| MAPE (%) | {gb_eval_result.get("mape", "N/A"):.2f} |
| Median AE | {gb_eval_result.get("median_absolute_error", "N/A"):.2f} |

---

## 📦 Baseline (DummyRegressor - Mean)

### Résultats d'Évaluation
| Métrique | Valeur |
|----------|--------|
| R² | {baseline_eval_result.get("r2", "N/A"):.4f} |
| MAE | {baseline_eval_result.get("mae", "N/A"):.2f} |
| RMSE | {baseline_eval_result.get("rmse", "N/A"):.2f} |
| MSE | {baseline_eval_result.get("mse", "N/A"):.2f} |
| MAPE (%) | {baseline_eval_result.get("mape", "N/A"):.2f} |
| Median AE | {baseline_eval_result.get("median_absolute_error", "N/A"):.2f} |

---

## 🏆 Comparaison et Rankings

**Meilleur modèle global** : `{comparison_result["summary"].get("best_overall", "N/A").upper()}`

### Points par Métrique
| Métrique | RF | GB | Baseline | Gagnant |
|----------|----|----|----------|---------|
"""

        # Ajouter rankings
        for metric, ranking in comparison_result.get("rankings", {}).items():
            if "winner" in ranking:
                rf_rank = ranking.get("random_forest", "-")
                gb_rank = ranking.get("gradient_boosting", "-")
                bl_rank = ranking.get("baseline", "-")
                winner = ranking.get("winner", "-").replace("_", " ").upper()
                log_content += (
                    f"| {metric} | {rf_rank} | {gb_rank} | {bl_rank} | {winner} |\n"
                )

        # Ajouter tableau des feature importances
        log_content += """

---

## 📊 Feature Importance

| Feature | RF Importance (%) | GB Importance (%) |
|---------|-------------------|-------------------|
"""

        # Récupérer les importances
        rf_importances = rf_eval_result.get("feature_importance", {})
        gb_importances = gb_eval_result.get("feature_importance", {})

        # Vérifier et normaliser en pourcentages si nécessaire
        rf_importances_pct = {}
        if rf_importances:
            total_rf = sum(rf_importances.values()) or 1
            # Si la somme est proche de 100, les valeurs sont déjà en pourcentages
            if 95 < total_rf < 105:
                rf_importances_pct = rf_importances
            else:
                rf_importances_pct = {
                    k: (v / total_rf * 100) for k, v in rf_importances.items()
                }

        gb_importances_pct = {}
        if gb_importances:
            total_gb = sum(gb_importances.values()) or 1
            # Si la somme est proche de 100, les valeurs sont déjà en pourcentages
            if 95 < total_gb < 105:
                gb_importances_pct = gb_importances
            else:
                gb_importances_pct = {
                    k: (v / total_gb * 100) for k, v in gb_importances.items()
                }

        # Trier par RF importance (ordre décroissant)
        sorted_features = sorted(
            rf_importances_pct.items(), key=lambda x: x[1], reverse=True
        )

        # Ajouter les lignes du tableau
        for feature, rf_imp_pct in sorted_features:
            gb_imp_pct = gb_importances_pct.get(feature, 0.0)
            log_content += f"| {feature} | {rf_imp_pct:.2f} | {gb_imp_pct:.2f} |\n"

        log_content += """

---

## 📌 Fichiers Sauvegardés

- ✅ Modèles (.pkl)
- ✅ Métriques (metrics.json)
- ✅ Données d'entraînement (CSV)
- ✅ Métadonnées de transformation (transformation_metadata.json)
- ✅ Scaler (scaler.pkl)
- ✅ Log d'entraînement (training_log.md)
"""

        with open(log_path, "w", encoding="utf-8") as f:
            f.write(log_content)

        logger.info(f"✅ Log d'entraînement sauvegardé: {log_path}")
        return str(log_path)

    except Exception as e:
        error_msg = (
            f"Erreur lors de la génération du log: {type(e).__name__} - {str(e)}"
        )
        logger.error(f"❌ {error_msg}")
        raise SerializationError(error_msg) from e
