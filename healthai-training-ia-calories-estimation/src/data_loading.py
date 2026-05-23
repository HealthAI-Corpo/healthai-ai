"""
Module de chargement des données
Responsable du chargement du CSV et des informations basiques
"""

import pandas as pd
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


class DataLoadingError(Exception):
    """Exception levée lors du chargement des données"""
    pass


def load_raw_data(filepath: str | Path) -> pd.DataFrame:
    """
    Charge les données brutes depuis un fichier CSV.

    Args:
        filepath: Chemin vers le fichier CSV

    Returns:
        pd.DataFrame: DataFrame avec les données brutes

    Raises:
        DataLoadingError: Erreur lors du chargement (fichier absent, format invalide, etc.)
    """
    filepath = Path(filepath)

    # Vérifier l'existence du fichier
    if not filepath.exists():
        error_msg = f"Fichier CSV introuvable : {filepath}"
        logger.error(f"❌ {error_msg}")
        raise DataLoadingError(error_msg)

    try:
        logger.info(f"📂 Chargement des données depuis {filepath}")
        df = pd.read_csv(filepath)

        # Vérifier que le DataFrame n'est pas vide
        if df.empty:
            error_msg = f"Le fichier CSV est vide : {filepath}"
            logger.error(f"❌ {error_msg}")
            raise DataLoadingError(error_msg)

        logger.info(f"✅ Données chargées : {df.shape[0]} lignes, {df.shape[1]} colonnes")
        return df

    except pd.errors.ParserError as e:
        error_msg = f"Erreur de parsing CSV (format invalide) : {str(e)}"
        logger.error(f"❌ {error_msg}")
        raise DataLoadingError(error_msg) from e
    
    except DataLoadingError:
        # Re-lever les DataLoadingError comme-is
        raise
    
    except Exception as e:
        error_msg = f"Erreur inattendue lors du chargement CSV : {type(e).__name__} - {str(e)}"
        logger.error(f"❌ {error_msg}")
        raise DataLoadingError(error_msg) from e
