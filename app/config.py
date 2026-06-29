from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str
    admin_token: str
    secret_key: str
    ip_hash_secret: str
    allowed_origins: str = "http://localhost:3000"
    contacts_fallback: str = ""
    zai_api_key: str = ""
    zai_api_base: str = "https://api.z.ai/api/coding/paas/v4"
    zai_model: str = "glm-4.7"
    chat_rate_per_hour: int = 50
    chat_rate_per_day: int = 300

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]

    @property
    def async_database_url(self) -> str:
        """URL для async-движка: psycopg → psycopg_async (psycopg3 async-mode).

        Sync `database_url` (psycopg) используется для Alembic/seed;
        async — для FastAPI-эндпоинтов.
        """
        url = self.database_url
        if url.startswith("postgresql+psycopg://"):
            return url.replace("postgresql+psycopg://", "postgresql+psycopg_async://", 1)
        return url


settings = Settings()
