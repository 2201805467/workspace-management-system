from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str
    session_hours: int = Field(default=8, ge=1, le=24)
    cookie_secure: bool = False  # Enable with HTTPS when deployed.
    file_storage_path: Path = Path(".data/files")
    max_upload_bytes: int = Field(default=10 * 1024 * 1024, ge=1, le=10 * 1024 * 1024)
    file_audit_interval_seconds: int = Field(default=3600, ge=60)
    index_poll_seconds: float = Field(default=2, ge=0.1, le=60)
    index_timeout_seconds: int = Field(default=15, ge=1, le=60)
    index_lease_seconds: int = Field(default=90, ge=90, le=600)
    index_max_text_chars: int = Field(default=100000, ge=1000, le=200000)
    index_max_pages: int = Field(default=200, ge=1, le=500)
    allowed_origins: list[str] = [
        "http://localhost:5173",
        "http://localhost:8080",
        "http://localhost:8000",
    ]
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
