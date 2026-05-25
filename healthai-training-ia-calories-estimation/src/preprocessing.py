"""
Module de prétraitement et normalisation des données
Responsable du nettoyage, feature engineering, encoding et normalisation
"""

import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler, MinMaxScaler
import logging

logger = logging.getLogger(__name__)


class PreprocessingError(Exception):
    """Exception levée lors du prétraitement"""

    pass


# ============================================================================
# 1. VALIDATION DES DONNEES
# ============================================================================


def validate_columns(df: pd.DataFrame, schema: dict) -> pd.DataFrame:
    """
    Vérifie les colonnes et leurs types, puis retourne uniquement
    les colonnes définies dans le schema.

    Args:
        df: DataFrame à vérifier
        schema: Dict {colonne: dtype_attendu}

    Returns:
        pd.DataFrame: DataFrame avec colonnes validées et réordonnées

    Raises:
        PreprocessingError: Si colonne manquante ou type incorrect
    """
    logger.info("🔍 Validation des colonnes...")

    colonnes_valides = []

    for colonne, dtype_attendu in schema.items():
        # Vérifie présence colonne
        if colonne not in df.columns:
            error_msg = f"Colonne requise manquante : '{colonne}'"
            logger.error(f"❌ {error_msg}")
            raise PreprocessingError(error_msg)

        # Vérifie type - STRICTE
        dtype_reel = str(df[colonne].dtype)

        if dtype_reel != dtype_attendu:
            error_msg = (
                f"Type INVALIDE pour '{colonne}' : "
                f"attendu={dtype_attendu}, reçu={dtype_reel}"
            )
            logger.error(f"❌ {error_msg}")
            raise PreprocessingError(error_msg)

        colonnes_valides.append(colonne)

    # Retourne uniquement les colonnes du schema, dans l'ordre
    df_clean = df[colonnes_valides].copy()
    logger.info(f"✅ Colonnes validées : {len(colonnes_valides)} colonnes")
    return df_clean


# ============================================================================
# 1B. CALCUL DE L'IMC (PHASE 6 MOD)
# ============================================================================


def compute_imc(df: pd.DataFrame) -> pd.DataFrame:
    """
    PHASE 6 MOD: Calcule l'IMC à partir de poids_kg et taille_cm.
    Formule: IMC = poids_kg / (taille_cm/100)²

    Puis supprime les colonnes poids_kg et taille_cm.

    Args:
        df: DataFrame contenant poids_kg et taille_cm

    Returns:
        pd.DataFrame: DataFrame avec colonne imc et sans poids/taille
    """
    df = df.copy()

    if "poids_kg" in df.columns and "taille_cm" in df.columns:
        logger.info("📐 Calcul de l'IMC (poids / taille²)...")

        # Vérifier qu'il n'y a pas de valeurs nulles
        if df[["poids_kg", "taille_cm"]].isnull().any().any():
            logger.error("❌ Valeurs nulles trouvées dans poids_kg ou taille_cm")
            raise PreprocessingError(
                "Impossible de calculer IMC avec des valeurs nulles"
            )

        # Calculer IMC = poids / (taille en mètres)²
        taille_m = df["taille_cm"] / 100.0
        df["imc"] = df["poids_kg"] / (taille_m**2)

        # Supprimer les colonnes originales
        df = df.drop(["poids_kg", "taille_cm"], axis=1)

        logger.info(
            f"  ✅ IMC calculé : min={df['imc'].min():.2f}, max={df['imc'].max():.2f}, mean={df['imc'].mean():.2f}"
        )
        return df
    else:
        logger.warning("⚠️  poids_kg ou taille_cm manquants, IMC non calculé")
        return df


# ============================================================================
# 2. GESTION DES VALEURS MANQUANTES
# ============================================================================


def handle_missing_values(df: pd.DataFrame) -> pd.DataFrame:
    """
    Gère les valeurs manquantes (NaN, None).

    Args:
        df: DataFrame

    Returns:
        pd.DataFrame: DataFrame nettoyé (lignes avec NaN supprimées)
    """
    missing_count_before = df.isnull().sum().sum()

    if missing_count_before > 0:
        rows_before = len(df)
        df = df.dropna()
        rows_after = len(df)
        rows_dropped = rows_before - rows_after

        logger.warning(f"⚠️  {missing_count_before} valeurs manquantes détectées")
        logger.info(f"🗑️  {rows_dropped} lignes supprimées (restantes: {rows_after})")
    else:
        logger.info("✅ Pas de valeurs manquantes")

    return df


# ============================================================================
# 3. ENCODING DES VARIABLES CATEGORIQUES
# ============================================================================


def encode_categorical(df: pd.DataFrame, categorical_mapping: dict) -> tuple:
    """
    Encode les colonnes catégoriques avec logiques spécifiques.

    1. SEXE : Accepte M/m/male/Male → 0, F/f/female/Female → 1
             Vérifie qu'après encoding, il n'y a que des 0/1
    2. TYPE_SPORT : One-Hot Encoding (colonne binaire par sport)

    Args:
        df: DataFrame
        categorical_mapping: Dict {colonne: mapping_strategy}

    Returns:
        tuple: (df_encoded, encoders_used)
    """
    df = df.copy()
    encoders_used = {}

    logger.info("🔤 Encoding des variables catégoriques...")

    # SEXE : Logique spécifique
    if "sexe" in df.columns:
        logger.info("  📊 Sexe: Normalisation (M/m/male→0, F/f/female→1)")

        sexe_mapping = categorical_mapping.get("sexe", {})

        # Appliquer le mapping
        df["sexe"] = df["sexe"].map(sexe_mapping)

        # Vérifier les valeurs inconnues
        invalid_count = df["sexe"].isnull().sum()
        if invalid_count > 0:
            logger.error(
                f"❌ {invalid_count} valeurs invalides pour 'sexe' détectées et supprimées"
            )
            df = df[df["sexe"].notna()]

        # Vérifier qu'il n'y a que des 0 et 1
        unique_values = df["sexe"].unique()
        if not set(unique_values).issubset({0, 1}):
            error_msg = (
                f"Sexe contient des valeurs invalides après encoding : {unique_values}"
            )
            logger.error(f"❌ {error_msg}")
            raise PreprocessingError(error_msg)

        encoders_used["sexe"] = sexe_mapping
        logger.info(f"  ✅ Sexe encodé : {len(df)} lignes conservées")

    # TYPE_SPORT : PHASE 6 MOD - Mapping simple (0/1) comme le sexe
    if "type_sport" in df.columns:
        logger.info("  📊 Type_Sport: Mapping simple (0=Cardio/HIIT, 1=Strength/Yoga)")

        sport_mapping = categorical_mapping.get("type_sport", {})

        # Appliquer le mapping
        df["type_sport"] = df["type_sport"].map(sport_mapping)

        # Vérifier les valeurs inconnues
        invalid_count = df["type_sport"].isnull().sum()
        if invalid_count > 0:
            logger.error(
                f"❌ {invalid_count} valeurs invalides pour 'type_sport' détectées et supprimées"
            )
            df = df[df["type_sport"].notna()]

        # Vérifier qu'il n'y a que des 0 et 1
        unique_values = df["type_sport"].unique()
        if not set(unique_values).issubset({0, 1}):
            error_msg = f"Type_sport contient des valeurs invalides après mapping : {unique_values}"
            logger.error(f"❌ {error_msg}")
            raise PreprocessingError(error_msg)

        encoders_used["type_sport"] = sport_mapping
        logger.info(
            f"  ✅ Type_sport encodé (0=Cardio, 1=Force) : {len(df)} lignes conservées"
        )

    logger.info(f"✅ {len(encoders_used)} colonnes catégoriques encodées")
    return df, encoders_used


# ============================================================================
# 4. NORMALISATION DES DONNEES NUMERIQUES
# ============================================================================


def normalize_numeric(
    X_train: pd.DataFrame, X_test: pd.DataFrame, method: str = "standard"
) -> tuple:
    """
    Normalise les colonnes numériques.

    Args:
        X_train: Features d'entraînement
        X_test: Features de test
        method: "standard" (StandardScaler) ou "minmax" (MinMaxScaler)

    Returns:
        tuple: (X_train_norm, X_test_norm, scaler)
               scaler à sauvegarder pour l'inversion en production
    """
    logger.info(f"📏 Normalisation des données ({method})...")

    numeric_cols = X_train.select_dtypes(include=[np.number]).columns.tolist()

    if method == "standard":
        scaler = StandardScaler()
    elif method == "minmax":
        scaler = MinMaxScaler()
    else:
        raise ValueError(f"Méthode inconnue: {method}")

    # Fit sur train, apply sur train et test
    X_train[numeric_cols] = scaler.fit_transform(X_train[numeric_cols])
    X_test[numeric_cols] = scaler.transform(X_test[numeric_cols])

    logger.info(f"✅ {len(numeric_cols)} colonnes numériques normalisées")
    return X_train, X_test, scaler


# ============================================================================
# 5. SPLIT TRAIN/TEST
# ============================================================================


def split_train_test(
    df: pd.DataFrame,
    target_col: str,
    features_cols: list,
    test_ratio: float = 0.2,
    random_state: int = 42,
) -> tuple:
    """
    Sépare les données en train/test.

    Args:
        df: DataFrame complet
        target_col: Nom de la colonne cible
        features_cols: Liste des colonnes de features
        test_ratio: Ratio de test (0.2 = 80 train / 20 test)
        random_state: Seed pour reproductibilité

    Returns:
        tuple: (X_train, X_test, y_train, y_test)
    """
    logger.info(
        f"📊 Split train/test ({(1 - test_ratio) * 100:.0f}% / {test_ratio * 100:.0f}%)..."
    )

    X = df[features_cols].copy()
    y = df[target_col].copy()

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=test_ratio, random_state=random_state
    )

    logger.info(
        f"✅ Split effectué:\n"
        f"   Train: {len(X_train)} samples\n"
        f"   Test:  {len(X_test)} samples"
    )

    return X_train, X_test, y_train, y_test


# ============================================================================
# 6. PIPELINE COMPLET DE PREPROCESSING
# ============================================================================


def fit_transform(
    df: pd.DataFrame,
    schema: dict,
    categorical_mapping: dict,
    features_cols: list,
    target_col: str,
    test_ratio: float = 0.2,
    random_state: int = 42,
    normalize: bool = True,
    scaling_method: str = "standard",
) -> dict:
    """
    Orchestre tout le preprocessing (Phase 1 complète).

    Étapes :
    1. Validation des colonnes (stricte)
    2. Suppression des NaN (simple)
    3. Encoding catégoriques (sexe + one-hot sport)
    4. Split train/test
    5. Normalisation

    Args:
        df: DataFrame brut
        schema: Schéma de validation
        categorical_mapping: Dict pour encoding catégoriques
        features_cols: Liste des colonnes de features
        target_col: Colonne cible
        test_ratio: Ratio test
        random_state: Seed
        normalize: Si True, normalise les données numériques
        scaling_method: "standard" ou "minmax"

    Returns:
        dict: Résultats et métadonnées
    """
    logger.info("=" * 70)
    logger.info("🚀 PREPROCESSING - Phase 1")
    logger.info("=" * 70)

    try:
        # 1. Validation des colonnes
        df = validate_columns(df, schema)

        # 1B. PHASE 6 MOD: Calcul de l'IMC
        df = compute_imc(df)

        # 2. Gestion des valeurs manquantes
        df = handle_missing_values(df)

        # 3. Encoding des variables catégoriques
        df, encoders = encode_categorical(df, categorical_mapping)

        # 4. Mettre à jour features_cols (type_sport a été remplacé + PHASE 6: poids/taille → IMC)
        # On garde la liste originale, mais elle sera ajustée après le split
        features_cols_updated = [col for col in features_cols if col in df.columns]

        # PHASE 6 MOD: Ajouter 'imc' si présent et pas déjà dans la liste
        if "imc" in df.columns and "imc" not in features_cols_updated:
            features_cols_updated.insert(
                0, "imc"
            )  # Insérer au début pour l'ordre cohérent

        # Ajouter les colonnes one-hot créées pour type_sport
        if encoders.get("type_sport", {}).get("method") == "onehot":
            onehot_cols = encoders["type_sport"]["columns"]
            features_cols_updated.extend(onehot_cols)

        logger.info(f"📊 Features finales : {len(features_cols_updated)} colonnes")

        # 5. Split train/test
        X_train, X_test, y_train, y_test = split_train_test(
            df,
            target_col,
            features_cols_updated,
            test_ratio=test_ratio,
            random_state=random_state,
        )

        # 6. Normalisation
        scaler = None
        if normalize:
            X_train, X_test, scaler = normalize_numeric(
                X_train, X_test, method=scaling_method
            )

        logger.info("=" * 70)
        logger.info("✅ PREPROCESSING TERMINE")
        logger.info("=" * 70)

        return {
            "X_train": X_train,
            "X_test": X_test,
            "y_train": y_train,
            "y_test": y_test,
            "encoders": encoders,
            "scaler": scaler,
            "split_counts": {
                "train": len(X_train),
                "test": len(X_test),
            },
            "features_cols_final": features_cols_updated,
        }

    except PreprocessingError as e:
        logger.error(f"❌ Erreur prétraitement : {e}")
        raise
    except Exception as e:
        logger.error(f"❌ Erreur inattendue : {type(e).__name__} - {e}")
        raise PreprocessingError(str(e)) from e
