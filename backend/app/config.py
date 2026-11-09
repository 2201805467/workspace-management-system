from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str
    session_hours: int = Field(default=8, ge=1, le=24)
    cookie_secure: bool = False  # Enable with HTTPS when deployed.
    allowed_origins: list[str] = ["http://localhost:5173", "http://localhost:8080", "http://localhost:8000"]
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
