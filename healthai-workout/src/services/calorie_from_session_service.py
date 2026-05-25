import time
from datetime import date, datetime

from fastapi import HTTPException
from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.database_mongo import mongo_db
from src.models.log_sante import LogSante
from src.models.log_seance import LogSeance
from src.models.profil_sante import ProfilSante
from src.models.utilisateur import Utilisateur
from src.services.calorie_service import CalorieService

# type_seance (libre en base) -> type_sport connu du modèle. Défaut : Cardio.
_SPORTS_CONNUS = {"Cardio", "HIIT", "Strength", "Yoga"}


def _normaliser_sexe(genre: str | None) -> str:
    """Ramène le genre stocké en base vers M / F (l'encodeur du modèle ne connaît que ça)."""
    if not genre:
        return "M"
    g = genre.strip().lower()
    if g.startswith("f"):  # Femme, Female, F, f
        return "F"
    return "M"  # Homme, Male, M, m, autre


def _normaliser_type_sport(type_seance: str | None) -> str:
    if type_seance and type_seance.strip() in _SPORTS_CONNUS:
        return type_seance.strip()
    return "Cardio"


def _calculer_age(naissance: date | None) -> int | None:
    if naissance is None:
        return None
    today = date.today()
    return today.year - naissance.year - ((today.month, today.day) < (naissance.month, naissance.day))


async def predict_from_session(
    service: CalorieService,
    id_seance: int,
    id_utilisateur: int,
    db: AsyncSession,
) -> dict:
    """Prédit les calories d'une séance enregistrée et met à jour log_seance.calorie_brulee."""
    start = time.perf_counter()

    # 1. Séance + vérification d'appartenance
    seance = (
        await db.execute(select(LogSeance).where(LogSeance.id_seance_log == id_seance))
    ).scalar_one_or_none()
    if seance is None:
        raise HTTPException(status_code=404, detail="Séance introuvable")
    if seance.id_utilisateur != id_utilisateur:
        raise HTTPException(status_code=403, detail="Cette séance n'appartient pas à l'utilisateur")

    calorie_brulee_avant = (
        float(seance.calorie_brulee) if seance.calorie_brulee is not None else None
    )

    # 2. Profil utilisateur + profil santé
    utilisateur = (
        await db.execute(select(Utilisateur).where(Utilisateur.id_utilisateur == id_utilisateur))
    ).scalar_one_or_none()
    if utilisateur is None:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable")

    profil = (
        await db.execute(select(ProfilSante).where(ProfilSante.id_utilisateur == id_utilisateur))
    ).scalar_one_or_none()

    # 3. Dernier relevé santé (bpm_repos, % gras)
    log_sante = (
        await db.execute(
            select(LogSante)
            .where(LogSante.id_utilisateur == id_utilisateur)
            .order_by(LogSante.date_log.desc())
        )
    ).scalars().first()

    # 4. Calcul de l'IMC (profil sinon dérivé poids/taille)
    imc = float(profil.imc) if profil and profil.imc is not None else None
    if imc is None and profil and profil.poids_kg and profil.taille_cm:
        taille_m = float(profil.taille_cm) / 100
        if taille_m > 0:
            imc = round(float(profil.poids_kg) / (taille_m**2), 1)

    # 5. Assemblage des features (None => imputé par la moyenne du dataset)
    #    - niveau_experience             : non disponible pour l'instant -> imputé
    features = {
        "imc": imc,
        "age": _calculer_age(utilisateur.date_de_naissance),
        "sexe": _normaliser_sexe(utilisateur.genre),
        "bpm_max": float(seance.bpm_max) if seance.bpm_max is not None else None,
        "bpm_moyen": float(seance.bpm_moyen) if seance.bpm_moyen is not None else None,
        "bpm_repos": log_sante.bpm_repos if log_sante else None,
        "duree_seance_minutes": float(seance.duree_minutes),
        "type_sport": _normaliser_type_sport(seance.type_seance),
        "pourcentage_gras": float(log_sante.pourcentage_gras)
        if log_sante and log_sante.pourcentage_gras is not None
        else None,
        "consommation_eau_ml": float(seance.consommation_eau_ml)
        if seance.consommation_eau_ml is not None
        else None,
        "niveau_experience": None,
    }

    # 6. Prédiction (predict_with_defaults impute les champs None restants)
    calories, imputed_features, original_values = service.predict_with_defaults(features)
    calories = round(calories, 2)

    # 7. Mise à jour en base
    seance.calorie_brulee = calories
    await db.commit()

    # 8. Trace MongoDB (best-effort)
    if mongo_db.db is not None:
        try:
            await mongo_db.db.predictions.insert_one(
                {
                    "endpoint": "predict-from-session",
                    "id_utilisateur": id_utilisateur,
                    "id_seance": id_seance,
                    "calories_estimees": calories,
                    "calorie_brulee_avant": calorie_brulee_avant,
                    "duree_traitement_ms": round((time.perf_counter() - start) * 1000, 1),
                    "timestamp": datetime.utcnow(),
                }
            )
        except Exception as e:  # noqa: BLE001
            logger.warning("Trace MongoDB predict-from-session échouée : {}", e)

    return {
        "id_seance": id_seance,
        "calories_estimees": calories,
        "calorie_brulee_avant": calorie_brulee_avant,
        "champs_utilises": {"fournis": original_values, "imputes": imputed_features},
    }
