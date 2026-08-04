"""Application settings loaded from environment / .env."""

from functools import lru_cache
from typing import List

from pydantic import field_validator
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

    # Gap extraction + web research (keep equal so every heading gets a summary)
    max_gaps: int = 5
    max_web_searches: int = 5

    vectorstore_root: str = "data/vectorstore"
    uploads_root: str = "data/uploads"

    # SMTP (mail / password change activation)
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = ""
    smtp_tls: bool = True
    smtp_ssl: bool = False

    security_code_ttl_minutes: int = 10
    security_code_cooldown_seconds: int = 60

    # OAuth (Google / GitHub) — leave empty to hide buttons
    public_base_url: str = "http://127.0.0.1:8000"
    google_client_id: str = ""
    google_client_secret: str = ""
    github_client_id: str = ""
    github_client_secret: str = ""

    @field_validator(
        "google_client_id",
        "google_client_secret",
        "github_client_id",
        "github_client_secret",
        "public_base_url",
        "smtp_host",
        "smtp_user",
        "smtp_password",
        "smtp_from",
        mode="before",
    )
    @classmethod
    def _strip_optional(cls, v):
        if isinstance(v, str):
            return v.strip()
        return v

    @property
    def cors_origin_list(self) -> List[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    def google_oauth_configured(self) -> bool:
        return bool(self.google_client_id and self.google_client_secret)

    def github_oauth_configured(self) -> bool:
        return bool(self.github_client_id and self.github_client_secret)


@lru_cache
def get_settings() -> Settings:
    return Settings()
