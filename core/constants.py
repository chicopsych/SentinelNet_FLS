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


# ═══════════════════════════════════════════════════════════════
# Topologia — OIDs SNMP padrão e categorias de incidente
# ═══════════════════════════════════════════════════════════════

# OIDs SNMP para coleta de tabelas de topologia
SNMP_OID_ARP_TABLE: str = "1.3.6.1.2.1.4.22"       # ipNetToMediaTable
SNMP_OID_MAC_TABLE_D1D: str = "1.3.6.1.2.1.17.4.3"  # dot1dTpFdbTable
SNMP_OID_MAC_TABLE_D1Q: str = "1.3.6.1.2.1.17.7.1.2"  # dot1qTpFdbTable
SNMP_OID_LLDP_REM: str = "1.0.8802.1.1.2.1.4"       # lldpRemTable
SNMP_OID_SYS_DESCR: str = "1.3.6.1.2.1.1.1.0"       # sysDescr.0

# Categorias de incidente de topologia
INCIDENT_CATEGORY_VLAN_DRIFT: str = "vlan_drift"
INCIDENT_CATEGORY_UNAUTHORIZED_NODE: str = "unauthorized_node"
