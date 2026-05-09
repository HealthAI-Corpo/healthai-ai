from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Configuration du serveur
    SERVICE_PORT: int = 8002

    # Connexions BDD (Pydantic ira chercher les valeurs dans le .env)
    MONGODB_URL: str = "mongodb://mongo:27017"
    MONGODB_DB_NAME: str = "healthai_workout"
    DATABASE_URL: str = ""  # On peut laisser vide si on veut forcer la lecture .env

    # ML
    MODEL_PATH: str = "/app/models/recommender_v1.joblib"


settings = Settings()
