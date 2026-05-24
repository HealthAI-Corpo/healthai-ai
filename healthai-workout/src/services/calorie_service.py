import logging

import numpy as np
from fastapi import HTTPException

logger = logging.getLogger(__name__)


class CalorieService:
    def __init__(self, model, scaler, metadata: dict):
        self.model = model
        self.scaler = scaler
        self.metadata = metadata
        self.features_order: list[str] = metadata.get("features_cols_order", [])
        self.encoders: dict = metadata.get("encoders", {})
        self.scaler_stats: dict = metadata.get("scaler_stats", {})

    def impute_missing_features(self, data: dict) -> tuple[dict, dict]:
        imputed = data.copy()
        imputed_features: dict = {}
        for feature in self.features_order:
            if imputed.get(feature) is None:
                if feature in self.scaler_stats:
                    mean_value = self.scaler_stats[feature].get("mean", 0)
                    imputed[feature] = mean_value
                    imputed_features[feature] = {"value": mean_value, "source": "scaler_stats_mean"}
                else:
                    raise HTTPException(
                        status_code=500,
                        detail=f"Impossible d'imputer {feature}: pas de stats disponibles",
                    )
        return imputed, imputed_features

    def _validate_input(self, data: dict) -> None:
        errors = []
        age = data.get("age", 0)
        if age < 15 or age > 100:
            errors.append("Age doit être entre 15 et 100")

        bpm_repos = data.get("bpm_repos", 0)
        bpm_moyen = data.get("bpm_moyen", 0)
        bpm_max = data.get("bpm_max", 0)
        if bpm_repos >= bpm_moyen:
            errors.append("BPM repos doit être < BPM moyen")
        if bpm_moyen >= bpm_max:
            errors.append("BPM moyen doit être < BPM max")

        duree = data.get("duree_seance_minutes", 0)
        if duree < 1 or duree > 480:
            errors.append("Durée de séance doit être entre 1 et 480 minutes")

        imc = data.get("imc", 0)
        if imc < 10 or imc > 50:
            errors.append("IMC doit être entre 10 et 50")

        pourcentage_gras = data.get("pourcentage_gras", 0)
        if pourcentage_gras < 0 or pourcentage_gras > 100:
            errors.append("Pourcentage de gras doit être entre 0 et 100")

        if errors:
            raise HTTPException(status_code=422, detail="; ".join(errors))

    def _encode_categorical_features(self, data: dict) -> dict:
        encoded = data.copy()
        if "sexe" in encoded:
            sexe_encoders = self.encoders.get("sexe", {})
            sexe_value = encoded["sexe"].strip()
            if sexe_value not in sexe_encoders:
                raise HTTPException(
                    status_code=422,
                    detail=f"Sexe invalide: {sexe_value}. Accepté: M ou F",
                )
            encoded["sexe"] = sexe_encoders[sexe_value]

        if "type_sport" in encoded:
            sport_encoders = self.encoders.get("type_sport", {})
            sport_value = encoded["type_sport"].strip()
            if sport_value not in sport_encoders:
                raise HTTPException(
                    status_code=422,
                    detail=f"Type de sport invalide: {sport_value}. Acceptés: Cardio, HIIT, Strength, Yoga",
                )
            encoded["type_sport"] = sport_encoders[sport_value]
        return encoded

    def _build_feature_vector(self, encoded_data: dict) -> np.ndarray:
        missing = [f for f in self.features_order if f not in encoded_data]
        if missing:
            raise HTTPException(
                status_code=422, detail=f"Features manquantes: {', '.join(missing)}"
            )
        return np.array([[encoded_data[f] for f in self.features_order]])

    def _normalize_features(self, feature_vector: np.ndarray) -> np.ndarray:
        try:
            return self.scaler.transform(feature_vector)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Erreur de normalisation: {e}") from e

    def predict(self, request_data: dict) -> float:
        try:
            self._validate_input(request_data)
            encoded = self._encode_categorical_features(request_data)
            vector = self._build_feature_vector(encoded)
            normalized = self._normalize_features(vector)
            return float(self.model.predict(normalized)[0])
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Erreur lors de la prédiction: {e}") from e

    def predict_with_defaults(self, request_data: dict) -> tuple[float, dict, dict]:
        try:
            original_values = {k: v for k, v in request_data.items() if v is not None}
            imputed_data, imputed_features = self.impute_missing_features(request_data)
            self._validate_input(imputed_data)
            encoded = self._encode_categorical_features(imputed_data)
            vector = self._build_feature_vector(encoded)
            normalized = self._normalize_features(vector)
            return float(self.model.predict(normalized)[0]), imputed_features, original_values
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=500, detail=f"Erreur lors de la prédiction avec defaults: {e}"
            ) from e
