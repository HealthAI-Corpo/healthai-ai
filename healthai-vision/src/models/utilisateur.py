from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship
from src.database import Base
# Import nécessaire pour que SQLAlchemy trouve la cible de la relation
from src.models.profilsante import ProfilSante 

class Utilisateur(Base):
    __tablename__ = "utilisateur"
    id_utilisateur = Column(Integer, primary_key=True)
    nom = Column(String(50))
    prenom = Column(String(50)) # Ajouté car présent dans ton SQL
    email = Column(String(255), unique=True)
    id_profil_sante = Column(Integer, ForeignKey("profil_sante.id_profil_sante"))
    
    # SQLAlchemy fera le lien automatiquement grâce à l'import en haut
    profil = relationship("ProfilSante")