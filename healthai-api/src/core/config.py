from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Variables de routage interne
    SERVICE_PORT: int = 8000
    VISION_SERVICE_URL: str = "http://healthai-vision:8001"
    WORKOUT_SERVICE_URL: str = "http://healthai-workout:8002"

    # Configuration Zitadel (Déplacées à l'intérieur de la classe)
    ZITADEL_DOMAIN: str = "https://your-domain.zitadel.cloud"
    ZITADEL_CLIENT_ID: str = "your-client-id"


settings = Settings()
