"""
Secrets Manager abstraction.

In dev (ENVIRONMENT=dev): reads secrets from environment variables via Settings.
In production:            fetches from AWS Secrets Manager at startup, cached for
                          the process lifetime (no per-request round-trips).

Interview talking point: "I wrote a unified secrets interface so application code
never branches on environment — the same get_secret() call works locally and in
production. Rotating a secret in Secrets Manager automatically takes effect on the
next container restart without a code change or redeploy."
"""

import json
import logging
from functools import lru_cache

from app.config import get_settings

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def load_secrets() -> dict:
    """
    Return a dict of secret key/value pairs.
    Dev: empty dict (Settings already reads from env vars).
    Production: full secrets payload from AWS Secrets Manager.
    """
    settings = get_settings()

    if settings.environment == "dev":
        return {}

    try:
        import boto3
        from botocore.exceptions import ClientError

        client = boto3.client("secretsmanager", region_name=settings.aws_region)
        response = client.get_secret_value(SecretId=settings.secret_name)
        secrets = json.loads(response["SecretString"])
        logger.info("Secrets loaded from AWS Secrets Manager: %s", settings.secret_name)
        return secrets
    except ImportError:
        logger.warning("boto3 not installed — falling back to environment variables")
        return {}
    except Exception as exc:
        logger.error("Failed to load secrets from Secrets Manager: %s", exc)
        raise
