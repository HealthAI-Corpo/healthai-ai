"""Accès à la table `utilisateur` côté gateway IA."""

from __future__ import annotations

from sqlalchemy import select

from src.core.database import get_session_maker
from src.models.utilisateur import Utilisateur


async def find_user_id_by_email(email: str) -> int | None:
    """Retourne `id_utilisateur` pour un email donné, ou None si introuvable."""
    async with get_session_maker()() as session:
        result = await session.execute(
            select(Utilisateur.id_utilisateur).where(Utilisateur.email == email)
        )
        return result.scalar_one_or_none()
