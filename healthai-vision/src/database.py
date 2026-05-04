from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base  
import os
from dotenv import load_dotenv

load_dotenv()

# On définit Base ici pour que tous les modèles puissent l'importer
Base = declarative_base()  # <--- Ajoute cette ligne

DATABASE_URL = os.getenv("DATABASE_URL")
engine = create_async_engine(DATABASE_URL, echo=True)

AsyncSessionLocal = async_sessionmaker(
    bind=engine, 
    class_=AsyncSession, 
    expire_on_commit=False
)