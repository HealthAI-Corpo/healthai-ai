from sqlalchemy import TIMESTAMP, Column, Date, Integer, String, text, ForeignKey
from sqlalchemy.orm import relationship

from src.database import Base

# Import nécessaire pour que SQLAlchemy trouve la cible de la relation


class Utilisateur(Base):
    __tablename__ = "utilisateur"
    id_utilisateur = Column(Integer, primary_key=True)
    nom = Column(String(50))
    prenom = Column(String(50))  # Ajouté car présent dans ton SQL
    email = Column(String(255), unique=True)
    date_de_naissance = Column(Date, nullable=False)
    genre = Column(String(50), nullable=False)
    mot_de_passe_hash = Column(String(255), nullable=False)
    type_abonnement = Column(String(50), server_default="Freemium")
    date_inscription = Column(TIMESTAMP, server_default=text("CURRENT_TIMESTAMP"))
    
    id_profil_sante = Column(Integer, ForeignKey("profil_sante.id_profil_sante"))

    # SQLAlchemy fera le lien automatiquement grâce à l'import en haut
    profil = relationship("ProfilSante")
