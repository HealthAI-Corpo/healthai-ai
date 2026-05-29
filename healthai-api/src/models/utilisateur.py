"""Modèle ORM minimal : seuls les champs nécessaires au mapping JWT -> id_utilisateur.

La table utilisateur est définie dans healthai-infra/db/
et reste la source de vérité, on n'expose ici que les colonnes lues par le gateway.
"""

from sqlalchemy import Column, Integer, String

from src.core.database import Base


class Utilisateur(Base):
    __tablename__ = "utilisateur"

    id_utilisateur = Column(Integer, primary_key=True)
    email = Column(String(255), nullable=False, unique=True)
