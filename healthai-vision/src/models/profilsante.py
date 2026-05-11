from sqlalchemy import Column, Integer, String, Numeric, Text
from src.database import Base 

class ProfilSante(Base):
    __tablename__ = "profil_sante"
    id_profil_sante = Column(Integer, primary_key=True)
    poids_kg = Column(Numeric(5, 2), nullable=False)
    taille_cm = Column(Integer)
    imc = Column(Numeric(4, 1))
    niveau_activite = Column(String(100))
    objectif_principal = Column(String(200))
    restrictions_alimentaires = Column(Text)