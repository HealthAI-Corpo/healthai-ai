"""Connexion Postgres asynchrone du gateway IA.

Le gateway n'a besoin du SQL que pour résoudre `email JWT -> id_utilisateur`.
L'engine est créé paresseusement pour permettre un démarrage en mode dev_stub
sans Postgres disponible.

Le driver (asyncpg, etc.) doit être présent dans `DATABASE_URL` côté config —
ex. `postgresql+asyncpg://user:pwd@host:5432/db`.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import declarative_base

from src.core.config import settings

Base = declarative_base()

_engine: AsyncEngine | None = None
_SessionLocal: async_sessionmaker[AsyncSession] | None = None


def get_engine() -> AsyncEngine:
    global _engine, _SessionLocal
    if _engine is None:
        if not settings.DATABASE_URL:
            raise RuntimeError(
                "DATABASE_URL non configurée — le mode JWKS nécessite Postgres "
                "pour résoudre l'id utilisateur."
            )
        _engine = create_async_engine(settings.DATABASE_URL, pool_pre_ping=True)
        _SessionLocal = async_sessionmaker(
            bind=_engine, class_=AsyncSession, expire_on_commit=False
        )
    return _engine


def get_session_maker() -> async_sessionmaker[AsyncSession]:
    get_engine()
    assert _SessionLocal is not None
    return _SessionLocal


async def dispose_engine() -> None:
    global _engine, _SessionLocal
    if _engine is not None:
        await _engine.dispose()
        _engine = None
        _SessionLocal = None
