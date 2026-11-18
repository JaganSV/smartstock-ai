"""Application settings, read from environment variables / `.env`."""

from functools import lru_cache
from pathlib import Path

from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import URL

# Repo-root .env (backend/app/core/config.py -> repo root), independent of the working directory.
# Absent in containers, where variables come from the environment.
_ENV_FILE = Path(__file__).resolve().parents[3] / ".env"


class Settings(BaseSettings):
    """Backend settings. Variable names match `.env.example`."""

    model_config = SettingsConfigDict(
        env_file=_ENV_FILE,
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",  # .env also carries frontend (VITE_*) variables
    )

    # Database
    postgres_user: str = "smartstock"
    postgres_password: SecretStr
    postgres_db: str = "smartstock"
    postgres_host: str = "db"
    postgres_port: int = 5432

    # Backend
    app_env: str = "local"
    log_level: str = "INFO"
    jwt_secret: SecretStr
    cors_allowed_origins: str = "http://localhost:5173"

    # watsonx.ai (used from Phase 5). All optional so the app starts without them.
    watsonx_url: str | None = None
    watsonx_api_key: SecretStr | None = None
    watsonx_project_id: str | None = None
    watsonx_api_version: str | None = None
    watsonx_chat_model_id: str | None = None
    watsonx_fallback_chat_model_id: str | None = None
    watsonx_embed_model_id: str | None = None

    @field_validator("cors_allowed_origins")
    @classmethod
    def _no_wildcard_origin(cls, value: str) -> str:
        if any(origin.strip() == "*" for origin in value.split(",")):
            raise ValueError("Wildcard CORS origins are not allowed")
        return value

    @property
    def cors_origins(self) -> list[str]:
        """Parsed list of allowed CORS origins."""
        return [o.strip() for o in self.cors_allowed_origins.split(",") if o.strip()]

    @property
    def sqlalchemy_url(self) -> URL:
        """SQLAlchemy URL (psycopg 3). Returned as an object so the password is never in a str."""
        return URL.create(
            drivername="postgresql+psycopg",
            username=self.postgres_user,
            password=self.postgres_password.get_secret_value(),
            host=self.postgres_host,
            port=self.postgres_port,
            database=self.postgres_db,
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
