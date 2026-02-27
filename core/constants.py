"""
core/constants.py
Constantes de domínio do SentinelNet_FLS.

Single source of truth para caminhos de banco de dados,
mapeamentos de severidade e status de incidentes.
"""

from __future__ import annotations

from pathlib import Path

# ── Caminho do banco de dados SQLite ─────────────────────────
DB_PATH: Path = (
    Path(__file__).resolve().parent.parent
    / "inventory"
    / "sentinel_data.db"
)

# ── Status de incidentes considerados "abertos" ─────────────
OPEN_INCIDENT_STATUSES: tuple[str, ...] = (
    "new",
    "novo",
    "em_analise",
)

# ── Mapeamento severidade → rank numérico ────────────────────
SEVERITY_RANK: dict[str, int] = {
    "CRITICAL": 5,
    "HIGH": 4,
    "MEDIUM": 3,
    "WARNING": 2,
    "LOW": 1,
    "INFO": 0,
}

# ── Mapeamento rank numérico → severidade ────────────────────
RANK_TO_SEVERITY: dict[int, str] = {
    5: "CRITICAL",
    4: "HIGH",
    3: "MEDIUM",
    2: "WARNING",
    1: "LOW",
    0: "INFO",
}

# ── Severidade → classe de status para a UI ──────────────────
SEVERITY_STATUS: dict[str, str] = {
    "CRITICAL": "critical",
    "HIGH": "warning",
    "MEDIUM": "warning",
    "WARNING": "warning",
    "LOW": "info",
    "INFO": "info",
}
