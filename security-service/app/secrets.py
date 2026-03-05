"""
Secrets loading — same pattern as auth-service and coffee-service.
In dev: reads from environment variables (already loaded by pydantic-settings).
In prod: fetches from AWS Secrets Manager and overrides the Settings cache.
"""

import json
import logging
from functools import lru_cache

from app.config import get_settings

logger = logging.getLogger(__name__)


def load_secrets() -> None:
    settings = get_settings()
    if settings.environment == "dev" or not settings.secret_name:
        return

    import boto3
    from botocore.exceptions import ClientError

    client = boto3.client("secretsmanager", region_name=settings.aws_region)
    try:
        response = client.get_secret_value(SecretId=settings.secret_name)
        secrets = json.loads(response["SecretString"])
        for key, value in secrets.items():
            if hasattr(settings, key.lower()):
                setattr(settings, key.lower(), value)
        logger.info("Secrets loaded from AWS Secrets Manager.")
    except ClientError as exc:
        logger.error("Failed to load secrets: %s", exc)
        raise
