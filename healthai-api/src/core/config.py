from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Lecture du fichier .env
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Variables attendues par main.py
    # Valeurs par défaut
    SERVICE_PORT: int = 8000
    VISION_SERVICE_URL: str = "http://healthai-vision:8001"
    WORKOUT_SERVICE_URL: str = "http://healthai-workout:8002"


# On crée l'instance que main.py essaie d'importer
settings = Settings()

# Config Zitadel
ZITADEL_DOMAIN: str
ZITADEL_CLIENT_ID: str
