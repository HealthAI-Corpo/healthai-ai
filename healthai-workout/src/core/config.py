from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    SERVICE_PORT: int = 8002
    LOG_LEVEL: str = "INFO"

    MONGODB_URL: str = "mongodb://mongo:27017"
    MONGODB_DB_NAME: str = "healthai_workout"
    DATABASE_URL: str = "postgresql+asyncpg://healthai:healthai@postgres:5432/healthai_db"

    INTERNAL_API_URL: str = "http://healthai-api:3000"
    INTERNAL_API_KEY: str = "change-me-min-32-chars-xxxxxxxxxxxxxxxx"

    OLLAMA_BASE_URL: str = "http://ollama:11434"
    OLLAMA_MODEL: str = "qwen2.5:0.5b"

    MODEL_PATH: str = "/app/models/CaloriesIA_1_0_0/random_forest/model.pkl"


settings = Settings()
