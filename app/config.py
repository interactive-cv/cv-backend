from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str
    admin_token: str
    secret_key: str
    ip_hash_secret: str
    allowed_origins: str = "http://localhost:3000"
    contacts_fallback: str = "vrg18@vk.com · Telegram @vrg18"
    zai_api_key: str = ""
    zai_api_base: str = "https://api.z.ai/api/paas/v4"
    zai_model: str = "glm-4.5"
    chat_rate_per_hour: int = 50
    chat_rate_per_day: int = 300

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]


settings = Settings()
