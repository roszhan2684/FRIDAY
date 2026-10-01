"""Backend configuration — loaded from .env or environment."""
from __future__ import annotations
from pathlib import Path
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Auth
    friday_backend_key: str = "dev-key-change-in-production"

    # Server
    friday_backend_port: int = 7800
    friday_backend_debug: bool = False

    # Database — defaults to local SQLite, override with Neon URL for prod
    database_url: str = "sqlite:///./friday_backend.db"

    # Cloudflare R2 (optional — gracefully disabled if not set)
    r2_account_id: str = ""
    r2_access_key_id: str = ""
    r2_secret_access_key: str = ""
    r2_endpoint_url: str = ""
    r2_bucket_audio: str = "friday-audio"
    r2_bucket_datasets: str = "friday-datasets"
    r2_bucket_models: str = "friday-models"

    # Default user (single-user app)
    friday_user_id: str = "user_default"
    friday_user_name: str = "Boss"
    friday_user_email: str = ""
    friday_user_timezone: str = "America/Los_Angeles"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

    @property
    def is_postgres(self) -> bool:
        return self.database_url.startswith("postgresql")

    @property
    def r2_configured(self) -> bool:
        return bool(
            self.r2_access_key_id
            and self.r2_secret_access_key
            and not self.r2_access_key_id.startswith("your-")
            and not self.r2_secret_access_key.startswith("your-")
        )


settings = Settings()
