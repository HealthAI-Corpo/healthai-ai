<<<<<<< HEAD
from sqlalchemy import TIMESTAMP, Column, Date, Integer, String, text
=======
from sqlalchemy import TIMESTAMP, Column, Date, ForeignKey, Integer, String, text
from sqlalchemy.orm import relationship
>>>>>>> chore/Olama-config

from src.database import Base

# Import nécessaire pour que SQLAlchemy trouve la cible de la relation


class Utilisateur(Base):
    __tablename__ = "utilisateur"
<<<<<<< HEAD

    id_utilisateur = Column(Integer, primary_key=True, index=True)
    nom = Column(String(50), nullable=False)
    prenom = Column(String(50), nullable=False)
    email = Column(String(255), nullable=False, unique=True, index=True)
=======
    id_utilisateur = Column(Integer, primary_key=True)
    nom = Column(String(50))
    prenom = Column(String(50))  # Ajouté car présent dans ton SQL
    email = Column(String(255), unique=True)
>>>>>>> chore/Olama-config
    date_de_naissance = Column(Date, nullable=False)
    genre = Column(String(50), nullable=False)
    mot_de_passe_hash = Column(String(255), nullable=False)
    type_abonnement = Column(String(50), server_default="Freemium")
    date_inscription = Column(TIMESTAMP, server_default=text("CURRENT_TIMESTAMP"))
<<<<<<< HEAD
=======

    id_profil_sante = Column(Integer, ForeignKey("profil_sante.id_profil_sante"))

    # SQLAlchemy fera le lien automatiquement grâce à l'import en haut
    profil = relationship("ProfilSante")
>>>>>>> chore/Olama-config
