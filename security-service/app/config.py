from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    environment: str = "dev"

    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/coffee"
    db_echo: bool = False

    redis_url: str = "redis://localhost:6379/0"
    auth_service_url: str = "http://localhost:8001"

    # Rate limiting thresholds
    rate_limit_max_failures: int = 5
    rate_limit_window_seconds: int = 60
    rate_limit_block_seconds: int = 900  # 15 minutes initial block

    # CORS — comma-separated string; split at usage point
    cors_origins: str = "http://localhost:3000"

    aws_region: str = "us-east-1"
    secret_name: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()
