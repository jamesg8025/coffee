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

    auth_service_url: str = "http://localhost:8001"

    # JWT — must match the values in auth-service so tokens can be validated locally
    jwt_secret: str = "change_me_in_production"
    jwt_algorithm: str = "HS256"

    # OpenAI — fetched from Secrets Manager in production
    openai_api_key: str = ""
    ai_recommendations_per_user_per_day: int = 10

    # CORS — comma-separated string; split at usage point
    cors_origins: str = "http://localhost:3000"

    aws_region: str = "us-east-1"
    secret_name: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()
