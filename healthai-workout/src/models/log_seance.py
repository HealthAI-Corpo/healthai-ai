from sqlalchemy import Column, DateTime, Integer, Numeric, String
from sqlalchemy.dialects.postgresql import JSONB

from src.database import Base


class LogSeance(Base):
    """Séance enregistrée. Le service IA lit la séance et met à jour calorie_brulee."""

    __tablename__ = "log_seance"

    id_seance_log = Column(Integer, primary_key=True)
    log_date = Column(DateTime, nullable=False)
    type_seance = Column(String(50))
    duree_minutes = Column(Numeric(5, 1), nullable=False)
    # Nullable : peut être vide tant que l'IA n'a pas estimé les calories
    calorie_brulee = Column(Numeric(6, 1), nullable=True)
    bpm_moyen = Column(Integer)
    # Features calories lues sur la séance (renseignées par le front, nullables)
    bpm_max = Column(Integer)
    consommation_eau_ml = Column(Numeric(7, 1))
    # Liste d'exercices (multi-exercices) + cycle de vie de la séance
    exercices = Column(JSONB)
    statut = Column(String(20))  # proposee | prevue | en_cours | terminee
    id_exercice = Column(Integer)
    id_utilisateur = Column(Integer, nullable=False, index=True)
