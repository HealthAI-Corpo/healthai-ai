from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    SERVICE_PORT: int = 8001
    # Spécifique à la Vision
    MODEL_NAME: str = "yolov8n.pt"