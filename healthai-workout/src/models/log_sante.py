from sqlalchemy import Column, DateTime, Integer, Numeric

from src.database import Base


class LogSante(Base):
    """Lecture seule — derniers relevés santé (bpm_repos, % gras) pour compléter la prédiction."""

    __tablename__ = "log_sante"

    id_log_sante = Column(Integer, primary_key=True)
    date_log = Column(DateTime)
    pourcentage_gras = Column(Numeric(4, 1))
    bpm_repos = Column(Integer)
    id_utilisateur = Column(Integer, nullable=False, index=True)
