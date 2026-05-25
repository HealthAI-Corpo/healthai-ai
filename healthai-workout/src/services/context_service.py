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
