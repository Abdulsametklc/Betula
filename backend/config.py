"""Application settings loaded from environment / .env."""

from functools import lru_cache
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    groq_api_key: str = ""
    # Fixed default — change only if you know you need another Groq model
    groq_model: str = "llama-3.3-70b-versatile"

    jwt_secret: str = "dev-insecure-change-me-to-32chars-min!!"
    jwt_expire_minutes: int = 60 * 24 * 7  # 7 days
    jwt_algorithm: str = "HS256"

    cors_origins: str = "http://localhost:3000,http://localhost:5173,http://127.0.0.1:5500"

    debug: bool = True
    seed_default_admin: bool = False
    database_path: str = "LocalInsights.db"

    # Conservative for Groq free-tier TPM
    max_gaps: int = 5
    max_web_searches: int = 3

    vectorstore_root: str = "data/vectorstore"
    uploads_root: str = "data/uploads"

    @property
    def cors_origin_list(self) -> List[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
