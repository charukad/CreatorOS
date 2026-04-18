from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = Field(default="development", alias="APP_ENV")
    api_host: str = Field(default="0.0.0.0", alias="API_HOST")
    api_port: int = Field(default=8000, alias="API_PORT")
    database_url: str = Field(
        default="postgresql+psycopg://creatoros:creatoros@localhost:5432/creatoros",
        alias="DATABASE_URL",
    )
    redis_url: str = Field(default="redis://localhost:6379/0", alias="REDIS_URL")
    storage_root: Path = Field(default=Path("storage"), alias="STORAGE_ROOT")
    downloads_root: Path = Field(default=Path("storage/downloads"), alias="DOWNLOADS_ROOT")
    secret_key: str = Field(default="dev-secret-key", alias="SECRET_KEY")
    default_user_email: str = Field(
        default="creatoros-local@example.com",
        alias="DEFAULT_USER_EMAIL",
    )
    default_user_name: str = Field(default="CreatorOS Local User", alias="DEFAULT_USER_NAME")
    cors_origins: list[str] = Field(
        default_factory=lambda: ["http://localhost:3000"],
        alias="CORS_ORIGINS",
    )

    model_config = SettingsConfigDict(
        env_file=("apps/api/.env", ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
