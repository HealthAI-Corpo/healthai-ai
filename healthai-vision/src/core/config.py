from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    SERVICE_PORT: int = 8001
    MODEL_NAME: str = "yolov8n.pt"
    MONGODB_URL: str = "mongodb://mongo:27017"
    MONGODB_DB_NAME: str = "healthai_db"


settings = Settings()
