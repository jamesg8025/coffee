"""
Secrets loading — same pattern as auth-service.

In dev, secrets come from environment variables (via .env).
In production, they're fetched from AWS Secrets Manager and cached in-process.
"""

import json
import logging
import os
from functools import lru_cache

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def _fetch_from_secrets_manager(secret_name: str, region: str) -> dict:
    import boto3
    client = boto3.client("secretsmanager", region_name=region)
    response = client.get_secret_value(SecretId=secret_name)
    return json.loads(response["SecretString"])


def load_secrets() -> None:
    """
    Populate environment variables from AWS Secrets Manager in production.
    In dev (secret_name not set), this is a no-op — env vars come from .env.
    """
    secret_name = os.getenv("SECRET_NAME", "")
    if not secret_name:
        return  # dev mode — env vars already loaded from .env

    region = os.getenv("AWS_REGION", "us-east-1")
    try:
        secrets = _fetch_from_secrets_manager(secret_name, region)
        for key, value in secrets.items():
            os.environ.setdefault(key.upper(), str(value))
        logger.info("Secrets loaded from AWS Secrets Manager: %s", secret_name)
    except Exception:
        logger.exception("Failed to load secrets from Secrets Manager — using env vars")
