from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    SERVICE_PORT: int = 8000
    LOG_LEVEL: str = "info"

    VISION_SERVICE_URL: str = "http://healthai-vision:8001"
    WORKOUT_SERVICE_URL: str = "http://healthai-workout:8002"

    DATABASE_URL: str = ""

    # AUTH_MODE = "jwks" : valide les tokens Zitadel via JWKS (production / infra).
    # AUTH_MODE = "dev_stub" : court-circuite l'auth, utile pour dev local sans Zitadel.
    AUTH_MODE: str = "dev_stub"
    DEV_STUB_USER_ID: int = 1
    DEV_STUB_USER_EMAIL: str = "dev@healthai.local"

    ZITADEL_ISSUER: str = ""
    JWT_AUDIENCE: str = ""
    # Vide = pas de check de rôle, juste authentification valide.
    ZITADEL_REQUIRED_ROLE: str = ""

    # Cache du mapping (sub|email) -> id_utilisateur en mémoire processus.
    USER_ID_CACHE_TTL_SECONDS: int = 300

    # Origines autorisées en CORS (CSV).
    CORS_ORIGINS: str = "http://localhost:3000"

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]


settings = Settings()
