import json
from pathlib import Path
from typing import Any

import numpy as np
from healthai_common.llm import LLMJsonError
from loguru import logger

from src.services import job_service
from src.services.llm_service import generate_llm_prediction_with_raw

# Schéma JSON envoyé à Ollama pour contraindre la séance produite (cf. system_prompt).
_SEANCE_SCHEMA = {
    "type": "object",
    "properties": {
        "titre": {"type": "string"},
        "duree_minutes": {"type": "integer"},
        "intensite": {"type": "string"},
        "exercices": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "nom": {"type": "string"},
                    "muscles_cibles": {"type": "array", "items": {"type": "string"}},
                    "series": {"type": "integer"},
                    "repetitions": {"type": "string"},
                    "repos_secondes": {"type": "integer"},
                    "conseil": {"type": "string"},
                },
                "required": ["nom"],
            },
        },
    },
    "required": ["titre", "duree_minutes", "intensite", "exercices"],
}


class RecommendationService:
    def __init__(self, model, le_type, le_int, metadata: dict):
        self.model = model
        self.le_type = le_type
        self.le_int = le_int
        self.metadata = metadata
        self.features: list[str] = metadata["features"]
        self.muscles: list[str] = metadata["muscles"]

    def predict_profile(self, profile: dict[str, Any]) -> dict[str, Any]:
        """Prédit type de séance, intensité et groupes musculaires depuis le profil biométrique."""
        age = float(profile.get("age", 30))
        poids = float(profile.get("poids_kg", 70))
        taille = float(profile.get("taille_cm", 170))
        imc = poids / (taille / 100) ** 2
        bpm_repos = float(profile.get("bpm_repos", 65))
        niveau = float(profile.get("niveau_experience", 1))
        freq = float(profile.get("frequence_sport_jour_semaine", 3))

        X = np.array([[age, imc, bpm_repos, niveau, freq]])
        pred = self.model.predict(X)[0]

        type_seance = self.le_type.inverse_transform([int(pred[0])])[0]
        intensite = self.le_int.inverse_transform([int(pred[1])])[0]
        muscles_cibles = [m for i, m in enumerate(self.muscles) if pred[2 + i] == 1]

        # Récupère les probabilités pour les scores de confiance
        probas = self.model.predict_proba(X)
        confidence = {
            "type_seance": round(float(max(probas[0][0])), 3),
            "intensite": round(float(max(probas[1][0])), 3),
        }

        return {
            "type_seance": type_seance,
            "intensite": intensite,
            "muscles_cibles": muscles_cibles,
            "confidence": confidence,
        }

    async def generate(self, profile: dict[str, Any], job_id: str | None = None) -> dict[str, Any]:
        """Pipeline complet : classifier → prompt → LLM → réponse enrichie.

        Si `job_id` est fourni, l'appel LLM (prompt + raw response) est tracé dans
        le job Mongo pour debug — succès comme échec JSON.
        """
        predictions = self.predict_profile(profile)
        logger.info(
            "Classifier → type={} intensite={} muscles={}",
            predictions["type_seance"],
            predictions["intensite"],
            predictions["muscles_cibles"],
        )

        muscles_str = ", ".join(predictions["muscles_cibles"]) or "full body"
        historique = profile.get("historique_seances", [])
        hist_text = (
            "\n".join(f"- {s}" for s in historique[-3:])
            if historique
            else "Aucune séance enregistrée."
        )

        system_prompt = """
Tu es un coach sportif expert de l'application HealthAI.
Tu génères des séances d'entraînement personnalisées en JSON strict, sans texte avant ni après.

Format JSON attendu :
{
  "titre": "Nom de la séance",
  "duree_minutes": 45,
  "intensite": "modérée",
  "exercices": [
    {
      "nom": "Nom de l'exercice",
      "muscles_cibles": ["muscle1"],
      "series": 3,
      "repetitions": "10-12",
      "repos_secondes": 90,
      "conseil": "Astuce technique"
    }
  ]
}
"""

        user_prompt = f"""
Profil de l'utilisateur :
- Âge : {profile.get("age", "?")} ans
- IMC : {round(float(profile.get("poids_kg", 70)) / (float(profile.get("taille_cm", 170)) / 100) ** 2, 1)}
- Niveau d'expérience : {profile.get("niveau_experience", 1)}/3
- Objectif : {profile.get("objectif", "Non précisé")}
- Restrictions : {profile.get("limitations", "Aucune")}

Recommandations du modèle IA :
- Type de séance : {predictions["type_seance"]}
- Intensité recommandée : {predictions["intensite"]}
- Groupes musculaires à cibler : {muscles_str}

Historique récent (éviter les mêmes groupes musculaires) :
{hist_text}

Génère une séance de 45 à 70 minutes respectant strictement le format JSON demandé.
"""

        try:
            raw_text, workout = await generate_llm_prediction_with_raw(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                response_format=_SEANCE_SCHEMA,
            )
        except LLMJsonError as exc:
            if job_id:
                await job_service.record_llm_call(
                    job_id,
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    raw_response=exc.raw_text,
                    parsed_ok=False,
                    error=str(exc.original) if exc.original else str(exc),
                )
            raise

        if job_id:
            await job_service.record_llm_call(
                job_id,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                raw_response=raw_text,
                parsed_ok=True,
            )

        return {
            "predictions_classifier": predictions,
            "seance": workout,
        }


def load_recommendation_service(models_dir: Path) -> "RecommendationService":
    import joblib

    reco_dir = models_dir / "RecoIA_1_0_0"
    required = ["model.pkl", "le_type.pkl", "le_intensite.pkl", "metadata.json"]
    missing = [f for f in required if not (reco_dir / f).exists()]
    if missing:
        raise FileNotFoundError(
            f"Fichiers manquants dans {reco_dir}: {missing}\n"
            "Générez le modèle avec: uv run python scripts/train_recommendation_model.py"
        )

    model = joblib.load(reco_dir / "model.pkl")
    le_type = joblib.load(reco_dir / "le_type.pkl")
    le_int = joblib.load(reco_dir / "le_intensite.pkl")
    with open(reco_dir / "metadata.json", encoding="utf-8") as f:
        metadata = json.load(f)

    logger.info(
        "RecommendationService chargé — CV F1={} F1 type={}",
        metadata.get("cv_f1_macro_mean"),
        metadata.get("f1_macro_type_seance"),
    )
    return RecommendationService(model, le_type, le_int, metadata)
