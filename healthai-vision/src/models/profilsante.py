from sqlalchemy import Column, Integer, String, Numeric, Text, ForeignKey
from src.database import Base 

class ProfilSante(Base):
    __tablename__ = "profil_sante"
    id_profil_sante = Column("id_profil", Integer, primary_key=True)

    id_utilisateur = Column(Integer, ForeignKey("utilisateur.id_utilisateur")) 

    poids_kg = Column(Numeric(5, 2), nullable=False)
    taille_cm = Column(Integer)
    imc = Column(Numeric(4, 1))
    niveau_activite = Column(String(100))
    objectif_principal = Column(String(200))
    restrictions_alimentaires = Column(Text)