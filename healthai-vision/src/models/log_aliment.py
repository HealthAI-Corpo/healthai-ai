from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, Numeric, String

from src.database import Base

# On importe TON modèle existant depuis son bon emplacement


class LogRepas(Base):
    """Modèle représentant la table log_aliment pour l'enregistrement d'un repas complet."""

    __tablename__ = "log_aliment"

    id_log_aliment = Column(Integer, primary_key=True, index=True)
    log_date = Column(DateTime, nullable=False, default=datetime.utcnow)
    repas = Column(String(50), nullable=False)
    quantite = Column(Numeric(7, 2), nullable=False, default=1.0)
    unite = Column(String(20), default="portion")

    # La clé étrangère pointe proprement sur ton modèle
    id_aliment = Column(Integer, ForeignKey("aliment.id_aliment"), nullable=False)
    id_utilisateur = Column(
        Integer, ForeignKey("utilisateur.id_utilisateur", ondelete="CASCADE"), nullable=False
    )
