"""Application settings, read from environment variables / `.env`."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import URL

# Repo-root .env (backend/app/core/config.py -> repo root), independent of the working directory.
# Absent in containers, where variables come from the environment.
_ENV_FILE = Path(__file__).resolve().parents[3] / ".env"

MIN_JWT_SECRET_BYTES = 32


class Settings(BaseSettings):
    """Backend settings. Variable names match `.env.example`."""

    model_config = SettingsConfigDict(
        env_file=_ENV_FILE,
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",  # .env also carries frontend (VITE_*) variables
        hide_input_in_errors=True,  # a rejected secret must never be echoed in the error text
    )

    # Database
    postgres_user: str = "smartstock"
    postgres_password: SecretStr
    postgres_db: str = "smartstock"
    postgres_host: str = "db"
    postgres_port: int = 5432
    # Integration-test database URL (contains the password, hence SecretStr). Optional.
    test_database_url: SecretStr | None = None

    # Backend
    app_env: str = "local"
    log_level: str = "INFO"
    jwt_secret: SecretStr
    jwt_algorithm: Literal["HS256"] = "HS256"  # fixed (ADR-015); any other value is rejected
    access_token_minutes: int = Field(default=60, ge=5, le=480)
    login_max_failures: int = Field(default=5, ge=1)
    login_lock_minutes: int = Field(default=15, ge=1)
    max_request_bytes: int = Field(default=1_048_576, ge=1)
    cors_allowed_origins: str = "http://localhost:5173"
    # FR-B5: recalculate once at startup. Unset = true when APP_ENV is "local", else false.
    recalc_on_startup: bool | None = None

    # Demo-user passwords: read only by `python -m app.cli seed-users`, never by the running app.
    seed_user_password_admin: SecretStr | None = None
    seed_user_password_manager: SecretStr | None = None
    seed_user_password_analyst: SecretStr | None = None
    seed_user_password_executive: SecretStr | None = None

    # watsonx.ai (used from Phase 5). All optional so the app starts without them.
    watsonx_url: str | None = None
    watsonx_api_key: SecretStr | None = None
    watsonx_project_id: str | None = None
    watsonx_api_version: str | None = None
    watsonx_chat_model_id: str | None = None
    watsonx_fallback_chat_model_id: str | None = None
    watsonx_embed_model_id: str | None = None

    @field_validator("jwt_secret")
    @classmethod
    def _jwt_secret_long_enough(cls, value: SecretStr) -> SecretStr:
        if len(value.get_secret_value().encode("utf-8")) < MIN_JWT_SECRET_BYTES:
            raise ValueError(f"JWT_SECRET must be at least {MIN_JWT_SECRET_BYTES} bytes")
        return value

    @field_validator("cors_allowed_origins")
    @classmethod
    def _no_wildcard_origin(cls, value: str) -> str:
        if any(origin.strip() == "*" for origin in value.split(",")):
            raise ValueError("Wildcard CORS origins are not allowed")
        return value

    @property
    def recalc_on_startup_enabled(self) -> bool:
        """The explicit RECALC_ON_STARTUP value, else True only for ``APP_ENV=local``."""
        if self.recalc_on_startup is not None:
            return self.recalc_on_startup
        return self.app_env == "local"

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
