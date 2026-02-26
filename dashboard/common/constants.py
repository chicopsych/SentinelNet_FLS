from __future__ import annotations

from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent.parent / "inventory" / "sentinel_data.db"

OPEN_INCIDENT_STATUSES = ("new", "em_analise")

SSE_MIN_SECONDS = 5
SSE_MAX_SECONDS = 300
SSE_DEFAULT_SECONDS = 30

SEVERITY_RANK = {
    "CRITICAL": 5,
    "HIGH": 4,
    "MEDIUM": 3,
    "WARNING": 2,
    "LOW": 1,
    "INFO": 0,
}

RANK_TO_SEVERITY = {
    5: "CRITICAL",
    4: "HIGH",
    3: "MEDIUM",
    2: "WARNING",
    1: "LOW",
    0: "INFO",
}

SEVERITY_STATUS = {
    "CRITICAL": "critical",
    "HIGH": "warning",
    "MEDIUM": "warning",
    "WARNING": "warning",
    "LOW": "info",
    "INFO": "info",
}
