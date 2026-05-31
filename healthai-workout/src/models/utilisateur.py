from sqlalchemy import Column, Date, Integer, String

from src.database import Base


class Utilisateur(Base):
    """Lecture seule — colonnes utiles à la prédiction (âge via naissance, sexe via genre)."""

    __tablename__ = "utilisateur"

    id_utilisateur = Column(Integer, primary_key=True)
    date_de_naissance = Column(Date, nullable=False)
    genre = Column(String(50), nullable=False)
