from sqlalchemy import Column, Integer, String, Date, TIMESTAMP, text

from src.database import Base

# Import nécessaire pour que SQLAlchemy trouve la cible de la relation


class Utilisateur(Base):
    __tablename__ = "utilisateur"

    id_utilisateur = Column(Integer, primary_key=True, index=True)
    nom = Column(String(50), nullable=False)
    prenom = Column(String(50), nullable=False)
    email = Column(String(255), nullable=False, unique=True, index=True)
    date_de_naissance = Column(Date, nullable=False)
    genre = Column(String(50), nullable=False)
    mot_de_passe_hash = Column(String(255), nullable=False)
    type_abonnement = Column(String(50), server_default="Freemium")
    date_inscription = Column(TIMESTAMP, server_default=text("CURRENT_TIMESTAMP"))
