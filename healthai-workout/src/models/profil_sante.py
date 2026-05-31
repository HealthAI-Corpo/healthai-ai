from sqlalchemy import Column, Integer, Numeric, String, Text

from src.database import Base


class ProfilSante(Base):
    """Lecture seule — données biométriques et objectifs de l'utilisateur."""

    __tablename__ = "profil_sante"

    id_profil = Column(Integer, primary_key=True)
    id_utilisateur = Column(Integer, nullable=False, index=True)
    poids_kg = Column(Numeric(5, 2))
    taille_cm = Column(Integer)
    imc = Column(Numeric(4, 1))
    niveau_activite = Column(String(100))
    type_maladie = Column(String(255))
    objectif_principal = Column(String(200))
    experience_sportive = Column(String(100))
    frequence_entrainement = Column(Integer)
    restrictions_alimentaires = Column(Text)
    allergies = Column(Text)
