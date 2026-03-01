"""
core/repositories/topology_repository.py
CRUD do inventário de topologia no SQLite.

Tabelas gerenciadas:
    topology_nodes  — Nós de rede correlacionados (L2/L3)
    topology_arp    — Entradas ARP (IP ↔ MAC)
    topology_mac    — Entradas MAC / bridge host
    topology_lldp   — Vizinhos LLDP / CDP
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from typing import Any

from core.constants import DB_PATH
from core.db import ensure_topology_tables
from internalloggin.logger import setup_logger

logger = setup_logger(__name__)


# ── Conexão ───────────────────────────────────────────────────────────────────

def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


# ═══════════════════════════════════════════════════════════════════════════════
# Nós de Rede (topology_nodes)
# ═══════════════════════════════════════════════════════════════════════════════


def upsert_node(
    customer_id: str,
    device_id: str,
    mac_address: str,
    *,
    ip_address: str | None = None,
    hostname: str | None = None,
    vlan_id: int | None = None,
    switch_port: str | None = None,
    vendor_oui: str | None = None,
    authorized: bool = False,
) -> None:
    """
    Insere ou atualiza um nó na tabela topology_nodes.

    Se o par (customer_id, mac_address) já existir, atualiza os campos
    mutáveis e o timestamp last_seen. O first_seen é preservado.
    """
    ensure_topology_tables()
    now = _utcnow_iso()
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO topology_nodes
                (customer_id, device_id, mac_address, ip_address, hostname,
                 vlan_id, switch_port, vendor_oui, first_seen, last_seen, authorized)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(customer_id, mac_address) DO UPDATE SET
                device_id   = excluded.device_id,
                ip_address  = excluded.ip_address,
                hostname    = COALESCE(excluded.hostname, topology_nodes.hostname),
                vlan_id     = excluded.vlan_id,
                switch_port = excluded.switch_port,
                vendor_oui  = COALESCE(excluded.vendor_oui, topology_nodes.vendor_oui),
                last_seen   = excluded.last_seen,
                authorized  = CASE
                    WHEN topology_nodes.authorized = 1 THEN 1
                    ELSE excluded.authorized
                END
            """,
            (
                customer_id, device_id, mac_address, ip_address, hostname,
                vlan_id, switch_port, vendor_oui, now, now, int(authorized),
            ),
        )
        conn.commit()


def list_nodes(
    customer_id: str | None = None,
    vlan_id: int | None = None,
) -> list[dict[str, Any]]:
    """Lista nós de topologia com filtros opcionais."""
    ensure_topology_tables()
    clauses: list[str] = []
    params: list[Any] = []
    if customer_id:
        clauses.append("customer_id = ?")
        params.append(customer_id)
    if vlan_id is not None:
        clauses.append("vlan_id = ?")
        params.append(vlan_id)

    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    sql = f"""
        SELECT id, customer_id, device_id, mac_address, ip_address,
               hostname, vlan_id, switch_port, vendor_oui,
               first_seen, last_seen, authorized
        FROM topology_nodes
        {where}
        ORDER BY last_seen DESC
    """
    with _connect() as conn:
        rows = conn.execute(sql, tuple(params)).fetchall()
    return [dict(r) for r in rows]


def get_node_by_mac(
    customer_id: str, mac_address: str,
) -> dict[str, Any] | None:
    """Retorna um nó específico pelo MAC."""
    ensure_topology_tables()
    with _connect() as conn:
        row = conn.execute(
            """
            SELECT * FROM topology_nodes
            WHERE customer_id = ? AND mac_address = ?
            """,
            (customer_id, mac_address),
        ).fetchone()
    return dict(row) if row else None


def set_node_authorized(
    customer_id: str, mac_address: str, authorized: bool,
) -> None:
    """Marca/desmarca um nó como autorizado."""
    ensure_topology_tables()
    with _connect() as conn:
        conn.execute(
            """
            UPDATE topology_nodes
            SET authorized = ?
            WHERE customer_id = ? AND mac_address = ?
            """,
            (int(authorized), customer_id, mac_address),
        )
        conn.commit()


def get_authorized_vlan_map(
    customer_id: str,
) -> dict[str, set[int]]:
    """
    Retorna MAC → {VLANs autorizadas} para nós autorizados de um customer.

    Usado pelo detector de VLAN Drift para verificar se um MAC está em
    uma VLAN não autorizada.
    """
    ensure_topology_tables()
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT mac_address, vlan_id FROM topology_nodes
            WHERE customer_id = ? AND authorized = 1 AND vlan_id IS NOT NULL
            """,
            (customer_id,),
        ).fetchall()

    result: dict[str, set[int]] = {}
    for row in rows:
        mac = row["mac_address"]
        vid = row["vlan_id"]
        result.setdefault(mac, set()).add(vid)
    return result


def list_nodes_by_vlan(customer_id: str) -> dict[int, list[dict[str, Any]]]:
    """Agrupa nós por VLAN ID."""
    nodes = list_nodes(customer_id=customer_id)
    grouped: dict[int, list[dict[str, Any]]] = {}
    for node in nodes:
        vid = node.get("vlan_id")
        if vid is not None:
            grouped.setdefault(vid, []).append(node)
    return grouped


# ═══════════════════════════════════════════════════════════════════════════════
# Tabela ARP (topology_arp)
# ═══════════════════════════════════════════════════════════════════════════════


def insert_arp_entries(
    customer_id: str,
    device_id: str,
    entries: list[dict[str, Any]],
) -> int:
    """Insere lote de entradas ARP. Retorna quantidade inserida."""
    if not entries:
        return 0
    ensure_topology_tables()
    now = _utcnow_iso()
    with _connect() as conn:
        conn.executemany(
            """
            INSERT INTO topology_arp
                (customer_id, device_id, ip_address, mac_address,
                 interface, vlan_id, collected_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    customer_id,
                    device_id,
                    e["ip_address"],
                    e["mac_address"],
                    e.get("interface"),
                    e.get("vlan_id"),
                    now,
                )
                for e in entries
            ],
        )
        conn.commit()
    return len(entries)


def list_arp_entries(
    customer_id: str,
    limit: int = 500,
) -> list[dict[str, Any]]:
    """Lista entradas ARP mais recentes de um customer."""
    ensure_topology_tables()
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT * FROM topology_arp
            WHERE customer_id = ?
            ORDER BY collected_at DESC
            LIMIT ?
            """,
            (customer_id, limit),
        ).fetchall()
    return [dict(r) for r in rows]


# ═══════════════════════════════════════════════════════════════════════════════
# Tabela MAC (topology_mac)
# ═══════════════════════════════════════════════════════════════════════════════


def insert_mac_entries(
    customer_id: str,
    device_id: str,
    entries: list[dict[str, Any]],
) -> int:
    """Insere lote de entradas MAC. Retorna quantidade inserida."""
    if not entries:
        return 0
    ensure_topology_tables()
    now = _utcnow_iso()
    with _connect() as conn:
        conn.executemany(
            """
            INSERT INTO topology_mac
                (customer_id, device_id, mac_address, interface,
                 vlan_id, switch_port, vendor_oui, is_local, collected_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    customer_id,
                    device_id,
                    e["mac_address"],
                    e.get("interface"),
                    e.get("vlan_id"),
                    e.get("switch_port"),
                    e.get("vendor_oui"),
                    int(e.get("is_local", False)),
                    now,
                )
                for e in entries
            ],
        )
        conn.commit()
    return len(entries)


def list_mac_entries(
    customer_id: str,
    limit: int = 500,
) -> list[dict[str, Any]]:
    """Lista entradas MAC mais recentes de um customer."""
    ensure_topology_tables()
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT * FROM topology_mac
            WHERE customer_id = ?
            ORDER BY collected_at DESC
            LIMIT ?
            """,
            (customer_id, limit),
        ).fetchall()
    return [dict(r) for r in rows]


# ═══════════════════════════════════════════════════════════════════════════════
# Tabela LLDP (topology_lldp)
# ═══════════════════════════════════════════════════════════════════════════════


def insert_lldp_entries(
    customer_id: str,
    device_id: str,
    entries: list[dict[str, Any]],
) -> int:
    """Insere lote de vizinhos LLDP. Retorna quantidade inserida."""
    if not entries:
        return 0
    ensure_topology_tables()
    now = _utcnow_iso()
    with _connect() as conn:
        conn.executemany(
            """
            INSERT INTO topology_lldp
                (customer_id, device_id, local_port, remote_device,
                 remote_port, remote_ip, remote_mac, remote_platform,
                 remote_description, collected_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    customer_id,
                    device_id,
                    e.get("local_port"),
                    e.get("remote_device"),
                    e.get("remote_port"),
                    e.get("remote_ip"),
                    e.get("remote_mac"),
                    e.get("remote_platform"),
                    e.get("remote_description"),
                    now,
                )
                for e in entries
            ],
        )
        conn.commit()
    return len(entries)


def list_lldp_entries(
    customer_id: str,
    limit: int = 500,
) -> list[dict[str, Any]]:
    """Lista vizinhos LLDP mais recentes de um customer."""
    ensure_topology_tables()
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT * FROM topology_lldp
            WHERE customer_id = ?
            ORDER BY collected_at DESC
            LIMIT ?
            """,
            (customer_id, limit),
        ).fetchall()
    return [dict(r) for r in rows]


# ═══════════════════════════════════════════════════════════════════════════════
# Estatísticas / KPIs
# ═══════════════════════════════════════════════════════════════════════════════


def count_nodes_by_customer(customer_id: str) -> int:
    """Total de nós de um customer."""
    ensure_topology_tables()
    with _connect() as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS cnt FROM topology_nodes WHERE customer_id = ?",
            (customer_id,),
        ).fetchone()
    return row["cnt"] if row else 0


def count_distinct_vlans(customer_id: str) -> int:
    """Total de VLANs distintas com nós associados."""
    ensure_topology_tables()
    with _connect() as conn:
        row = conn.execute(
            """
            SELECT COUNT(DISTINCT vlan_id) AS cnt
            FROM topology_nodes
            WHERE customer_id = ? AND vlan_id IS NOT NULL
            """,
            (customer_id,),
        ).fetchone()
    return row["cnt"] if row else 0
