"""
Script principal - Phase 5
Pipeline complet d'entraînement : Phases 1 à 4
Sauvegarde automatique des modèles et résultats
"""

import sys
import logging
from sklearn.dummy import DummyRegressor
from src.data_loading import load_raw_data
from src.preprocessing import fit_transform
from src.model_training import train_random_forest, train_gradient_boosting
from src.model_evaluation import evaluate_model, compare_models
from src.model_serialization import (
    get_next_version_dir,
    save_model,
    save_metrics,
    save_training_data,
    save_scaler,
    save_transformation_metadata,
    save_training_log,
)

# Configurer l'encodage UTF-8 pour stdout (Windows)
if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")

# Configuration logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s - %(name)s - %(message)s")
logger = logging.getLogger(__name__)

# Imports locaux
from config import (
    CSV_FILE,
    SCHEMA,
    FEATURES_COLS,
    TARGET_COL,
    CATEGORICAL_COLS,
    TRAIN_TEST_SPLIT_RATIO,
    RANDOM_STATE,
    NORMALIZE_NUMERIC,
    SCALING_METHOD,
    RF_PARAMS,
    GB_PARAMS,
    DATA_MODELS_DIR,
    MODEL_NAME,
    VERSION_MAJOR,
)



def main():
    """
    Exécute le pipeline complet d'entraînement (Phase 1 à 4)

    Étapes :
    1. Charger et préparer les données
    2. Entraîner Random Forest et Gradient Boosting
    3. Évaluer les modèles
    4. Sauvegarder tous les artefacts

    Returns:
        int: 0 si succès, 1 si erreur
    """

    try:
        # ====================================================================
        # PHASE 1 : Préparation des données
        # ====================================================================
        logger.info("📥 Phase 1 - Chargement des données brutes")
        df_raw = load_raw_data(CSV_FILE)
        logger.info(f"✅ {df_raw.shape[0]} lignes chargées")

        logger.info("📋 Phase 1 - Preprocessing")
        preprocessing_result = fit_transform(
            df=df_raw,
            schema=SCHEMA,
            categorical_mapping=CATEGORICAL_COLS,
            features_cols=FEATURES_COLS,
            target_col=TARGET_COL,
            test_ratio=1 - TRAIN_TEST_SPLIT_RATIO,
            random_state=RANDOM_STATE,
            normalize=NORMALIZE_NUMERIC,
            scaling_method=SCALING_METHOD,
        )

        X_train = preprocessing_result["X_train"]
        X_test = preprocessing_result["X_test"]
        y_train = preprocessing_result["y_train"]
        y_test = preprocessing_result["y_test"]
        encoders = preprocessing_result["encoders"]
        scaler = preprocessing_result["scaler"]
        features_cols_final = preprocessing_result["features_cols_final"]

        logger.info(
            f"✅ Preprocessing terminé ({X_train.shape[0]} train / {X_test.shape[0]} test)"
        )

        # ====================================================================
        # PHASE 2 : Entraînement des modèles
        # ====================================================================
        logger.info("🌲 Phase 2 - Entraînement Random Forest")
        rf_result = train_random_forest(X_train, y_train, params=RF_PARAMS)
        rf_model = rf_result["model"]
        logger.info(f"✅ RF entraîné en {rf_result['training_time_seconds']:.2f}s")

        logger.info("🚀 Phase 2 - Entraînement Gradient Boosting")
        gb_result = train_gradient_boosting(X_train, y_train, params=GB_PARAMS)
        gb_model = gb_result["model"]
        logger.info(f"✅ GB entraîné en {gb_result['training_time_seconds']:.2f}s")

        logger.info("📦 Phase 2 - Entraînement Baseline")
        baseline_model = DummyRegressor(strategy="mean")
        baseline_model.fit(X_train, y_train)
        logger.info("✅ Baseline entraîné")

        # ====================================================================
        # PHASE 3 : Évaluation
        # ====================================================================
        logger.info("📊 Phase 3 - Évaluation des modèles")
        rf_eval = evaluate_model(rf_model, X_test, y_test)
        gb_eval = evaluate_model(gb_model, X_test, y_test)
        baseline_eval = evaluate_model(baseline_model, X_test, y_test)

        #rf_quality = evaluate_metrics(rf_eval, METRICS_THRESHOLDS)
        #gb_quality = evaluate_metrics(gb_eval, METRICS_THRESHOLDS)
        #baseline_quality = evaluate_metrics(baseline_eval, METRICS_THRESHOLDS)

        comparison = compare_models(rf_eval, gb_eval, baseline_eval)
        logger.info(
            f"✅ Évaluation terminée - Meilleur : {comparison['summary']['best_overall']}"
        )

        # ====================================================================
        # PHASE 4 : Sauvegarde des modèles et résultats
        # ====================================================================
        logger.info("💾 Phase 4 - Génération de la version")
        version_dir, version_string = get_next_version_dir(
            MODEL_NAME, VERSION_MAJOR, DATA_MODELS_DIR
        )
        logger.info(f"✅ Version générée : {version_string}")

        logger.info("💾 Phase 4 - Sauvegarde des modèles")
        rf_model_path = save_model(
            rf_model, "RandomForest", version_dir, "random_forest"
        )
        gb_model_path = save_model(
            gb_model, "GradientBoosting", version_dir, "gradient_boosting"
        )
        logger.info("✅ Modèles sauvegardés")

        logger.info("📊 Phase 4 - Sauvegarde des métriques")
        rf_metrics_path = save_metrics(rf_eval, version_dir, "random_forest")
        gb_metrics_path = save_metrics(gb_eval, version_dir, "gradient_boosting")
        logger.info("✅ Métriques sauvegardées")

        logger.info("💾 Phase 4 - Sauvegarde des données d'entraînement")
        data_paths = save_training_data(
            X_train, X_test, y_train, y_test, df_raw, version_dir
        )
        logger.info("✅ Données d'entraînement sauvegardées")

        logger.info("📏 Phase 4 - Sauvegarde du scaler")
        scaler_path = save_scaler(scaler, version_dir)
        logger.info("✅ Scaler sauvegardé")

        logger.info("🔑 Phase 4 - Sauvegarde des métadonnées de transformation")
        metadata_path = save_transformation_metadata(
            scaler, encoders, features_cols_final, version_dir
        )
        logger.info("✅ Métadonnées sauvegardées")

        logger.info("📝 Phase 4 - Génération du log d'entraînement")
        log_path = save_training_log(
            version_string,
            rf_result,
            gb_result,
            rf_eval,
            gb_eval,
            baseline_eval,
            comparison,
            len(X_train),
            len(X_test),
            version_dir,
        )
        logger.info("✅ Log d'entraînement généré")

        # ====================================================================
        # RÉSUMÉ FINAL
        # ====================================================================
        logger.info("=" * 80)
        logger.info("✨ PIPELINE COMPLET EXÉCUTÉ AVEC SUCCÈS ✨")
        logger.info("=" * 80)
        logger.info(f"Version : {version_string}")
        logger.info(f"Répertoire : {version_dir}")
        logger.info(
            f"Meilleur modèle : {comparison['summary']['best_overall'].upper()}"
        )
        logger.info(
            f"RF: {comparison['summary']['random_forest']} points | GB: {comparison['summary']['gradient_boosting']} points"
        )
        logger.info("=" * 80)

        return 0

    except Exception as e:
        logger.error(f"❌ Erreur lors de l'exécution : {type(e).__name__} - {str(e)}")
        logger.exception("Traceback complet :")
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
