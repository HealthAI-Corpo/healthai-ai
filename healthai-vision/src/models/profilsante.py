from sqlalchemy import Column, ForeignKey, Integer, Numeric, String, Text

from src.database import Base


class ProfilSante(Base):
    __tablename__ = "profil_sante"

    id_profil = Column(Integer, primary_key=True, index=True)
    id_utilisateur = Column(
        Integer,
        ForeignKey("utilisateur.id_utilisateur", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    poids_kg = Column(Numeric(5, 2))
    taille_cm = Column(Integer)
    imc = Column(Numeric(4, 1))
    niveau_activite = Column(String(100))
    type_maladie = Column(String(255))
    severite = Column(String(50))
    restrictions_alimentaires = Column(Text)
    allergies = Column(Text)
    objectif_principal = Column(String(200))
    experience_sportive = Column(String(100))
    frequence_entrainement = Column(Integer)
