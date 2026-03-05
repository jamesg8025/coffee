"""
Celery task: automated dependency vulnerability scan.

Uses pip-audit to check all installed packages against PyPI's advisory
database and the OSV vulnerability database. Results are stored in the
security_scan_log table for review via the scan history API.

pip-audit is maintained by the Python Security Steering Council.
It requires no API key and pulls advisories directly from PyPI.

Interview talking point:
  "Safety caught a critical vulnerability in one of my transitive
  dependencies during development. That's exactly the value of shifting
  security left — automated scanning catches things before they ship."
"""

import json
import logging
import subprocess
from datetime import datetime, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.celery_app import celery_app
from app.config import get_settings
from app.models.security import SecurityScanLog

logger = logging.getLogger(__name__)


def _get_sync_session() -> sessionmaker:
    """
    Create a synchronous SQLAlchemy session for use inside Celery tasks.

    Celery workers are synchronous; we swap the asyncpg driver for psycopg2.
    The FastAPI app continues using the async engine in app/database.py.
    """
    settings = get_settings()
    sync_url = settings.database_url.replace("+asyncpg", "+psycopg2")
    engine = create_engine(sync_url, pool_pre_ping=True)
    return sessionmaker(engine, expire_on_commit=False)


@celery_app.task(name="app.tasks.scanner.run_dependency_scan", bind=True, max_retries=3)
def run_dependency_scan(self) -> dict:
    """
    Run pip-audit and store findings in security_scan_log.

    Returns a summary dict (also stored as Celery task result).
    """
    logger.info("Starting dependency vulnerability scan (pip-audit).")

    try:
        result = subprocess.run(
            ["pip-audit", "--format", "json", "--progress-spinner", "off"],
            capture_output=True,
            text=True,
            timeout=180,
        )
    except FileNotFoundError:
        logger.error("pip-audit not found — is it installed in this container?")
        _store_scan_log(
            scan_type="dependency",
            findings={"error": "pip-audit binary not found"},
            severity="ERROR",
        )
        return {"status": "error", "detail": "pip-audit not found"}
    except subprocess.TimeoutExpired:
        logger.error("pip-audit timed out.")
        _store_scan_log(
            scan_type="dependency",
            findings={"error": "scan timed out after 180 seconds"},
            severity="ERROR",
        )
        return {"status": "error", "detail": "timeout"}

    # pip-audit exits 1 when vulnerabilities found, 0 when clean.
    try:
        data = json.loads(result.stdout) if result.stdout.strip() else {}
    except json.JSONDecodeError:
        data = {"raw_output": result.stdout[:2000]}

    dependencies = data.get("dependencies", [])
    vulnerable = [d for d in dependencies if d.get("vulns")]

    severity = "NONE"
    if vulnerable:
        # pip-audit doesn't assign severity levels itself, so we use
        # the presence of a fix version as a proxy for actionability.
        has_fix = any(
            any(v.get("fix_versions") for v in d["vulns"])
            for d in vulnerable
        )
        severity = "HIGH" if has_fix else "MEDIUM"

    findings = {
        "scanned_at": datetime.now(timezone.utc).isoformat(),
        "total_packages": len(dependencies),
        "vulnerable_packages": len(vulnerable),
        "vulnerabilities": [
            {
                "package": d["name"],
                "version": d["version"],
                "vulns": d["vulns"],
            }
            for d in vulnerable
        ],
        "exit_code": result.returncode,
    }

    _store_scan_log(scan_type="dependency", findings=findings, severity=severity)

    summary = {
        "status": "complete",
        "severity": severity,
        "total_packages": findings["total_packages"],
        "vulnerable_packages": findings["vulnerable_packages"],
    }
    logger.info("Scan complete: %s", summary)
    return summary


def _store_scan_log(scan_type: str, findings: dict, severity: str) -> None:
    """Write a scan result row to the database (synchronous)."""
    SessionLocal = _get_sync_session()
    with SessionLocal() as session:
        log = SecurityScanLog(
            scan_type=scan_type,
            findings=findings,
            severity=severity,
        )
        session.add(log)
        session.commit()
