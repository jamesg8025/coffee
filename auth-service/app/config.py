from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    environment: str = "dev"

    # Database
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/coffee"
    db_echo: bool = False

    # JWT — Phase 2 will wire these into auth flows
    jwt_secret: str = "dev-jwt-secret-replace-in-production"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 7

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Rate limiting — shared with security-service (same Redis keys)
    rate_limit_max_failures: int = 5
    rate_limit_window_seconds: int = 60
    rate_limit_block_seconds: int = 900  # 15 min initial block; doubles each time

    # CORS — comma-separated string; split at usage point to avoid pydantic-settings
    # JSON-decoding list fields before validators can run
    cors_origins: str = "http://localhost:3000"

    # AWS Secrets Manager (production only)
    aws_region: str = "us-east-1"
    secret_name: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()
