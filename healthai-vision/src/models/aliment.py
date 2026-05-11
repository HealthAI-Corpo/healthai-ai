from sqlalchemy import Column, Integer, String, Numeric
from src.database import Base  

class Aliment(Base):
    __tablename__ = "aliment"

    id_aliment = Column(Integer, primary_key=True, index=True)
    nom = Column(String(255), nullable=False)
    categorie = Column(String(100))
    type_repas = Column(String(50))

    calories = Column(Numeric(6, 1), nullable=False)
    proteines = Column(Numeric(5, 2), nullable=False)
    lipides = Column(Numeric(5, 2), nullable=False)
    glucides = Column(Numeric(5, 2), nullable=False)

    fibres = Column(Numeric(5, 2))
    sucres = Column(Numeric(5, 2))
    sodium_mg = Column(Numeric(7, 2))
    cholesterol_mg = Column(Numeric(7, 2))
    eau_ml = Column(Numeric(7, 2))
    

    #unite_mesure = Column(String(50), server_default="portion")