"""Construction du contexte utilisateur depuis PostgreSQL (pour les endpoints IA Ollama).

Le front ne fournit plus le contexte : on le reconstruit à partir de l'id utilisateur
(profil + utilisateur) et de l'historique récent des séances.
"""

from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.log_seance import LogSeance
from src.models.profil_sante import ProfilSante
from src.models.utilisateur import Utilisateur


def _calculer_age(naissance: date | None) -> int | None:
    if naissance is None:
        return None
    today = date.today()
    avant_anniversaire = (today.month, today.day) < (naissance.month, naissance.day)
    return today.year - naissance.year - avant_anniversaire


async def get_user_context(db: AsyncSession, user_id: int) -> dict | None:
    """Renvoie le contexte utilisateur, ou None si l'utilisateur n'existe pas."""
    utilisateur = (
        await db.execute(select(Utilisateur).where(Utilisateur.id_utilisateur == user_id))
    ).scalar_one_or_none()
    if utilisateur is None:
        return None

    profil = (
        await db.execute(select(ProfilSante).where(ProfilSante.id_utilisateur == user_id))
    ).scalar_one_or_none()

    imc = None
    if profil and profil.imc is not None:
        imc = float(profil.imc)
    elif profil and profil.poids_kg and profil.taille_cm:
        taille_m = float(profil.taille_cm) / 100
        if taille_m > 0:
            imc = round(float(profil.poids_kg) / (taille_m**2), 1)

    return {
        "age": _calculer_age(utilisateur.date_de_naissance),
        "sexe": utilisateur.genre,
        "poids_kg": float(profil.poids_kg) if profil and profil.poids_kg is not None else None,
        "taille_cm": profil.taille_cm if profil else None,
        "imc": imc,
        "niveau_activite": profil.niveau_activite if profil else None,
        "experience_sportive": profil.experience_sportive if profil else None,
        "objectif_principal": profil.objectif_principal if profil else None,
        "frequence_entrainement": profil.frequence_entrainement if profil else None,
        "type_maladie": profil.type_maladie if profil else None,
        "restrictions_alimentaires": profil.restrictions_alimentaires if profil else None,
        "allergies": profil.allergies if profil else None,
    }


async def get_recent_sessions(db: AsyncSession, user_id: int, limit: int = 5) -> list[dict]:
    """Renvoie les dernières séances de l'utilisateur (plus récentes d'abord)."""
    seances = (
        (
            await db.execute(
                select(LogSeance)
                .where(LogSeance.id_utilisateur == user_id)
                .order_by(LogSeance.log_date.desc())
                .limit(limit)
            )
        )
        .scalars()
        .all()
    )
    return [
        {
            "date": s.log_date.isoformat() if s.log_date else None,
            "type_seance": s.type_seance,
            "duree_minutes": float(s.duree_minutes) if s.duree_minutes is not None else None,
            "statut": s.statut,
            "exercices": s.exercices,
        }
        for s in seances
    ]


# Le profil santé stocke l'expérience en texte ; le classifier de reco attend un niveau 1-3.
_EXPERIENCE_TO_NIVEAU = {
    "débutant": 1,
    "debutant": 1,
    "novice": 1,
    "intermédiaire": 2,
    "intermediaire": 2,
    "avancé": 3,
    "avance": 3,
    "expert": 3,
}


def _niveau_experience(experience_sportive: str | None) -> int:
    if not experience_sportive:
        return 1
    return _EXPERIENCE_TO_NIVEAU.get(experience_sportive.strip().lower(), 1)


async def build_recommendation_profile(db: AsyncSession, user_id: int) -> dict | None:
    """Assemble le profil attendu par /recommendations/workout à partir de la base.

    Renvoie None si l'utilisateur n'existe pas. Les champs absents (None) sont omis
    afin que le service applique ses propres valeurs par défaut.
    """
    context = await get_user_context(db, user_id)
    if context is None:
        return None

    recent = await get_recent_sessions(db, user_id)
    historique = [
        f"{s.get('date')} : {s.get('type_seance') or 'séance'} ({s.get('duree_minutes')} min)"
        for s in recent
    ]

    profile = {
        "age": context.get("age"),
        "poids_kg": context.get("poids_kg"),
        "taille_cm": context.get("taille_cm"),
        "niveau_experience": _niveau_experience(context.get("experience_sportive")),
        "frequence_sport_jour_semaine": context.get("frequence_entrainement"),
        "objectif": context.get("objectif_principal"),
        "limitations": context.get("type_maladie"),
        "historique_seances": historique,
    }
    return {k: v for k, v in profile.items() if v is not None}
