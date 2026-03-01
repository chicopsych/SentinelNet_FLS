"""
core/db.py
Utilitário de acesso ao banco de dados SQLite.

Funções compartilhadas por todos os repositórios do sistema.
"""

from __future__ import annotations

import sqlite3
from typing import Any

from core.constants import DB_PATH


def db_exists() -> bool:
    """Retorna True se o arquivo do banco de dados existir."""
    return DB_PATH.exists()


def query_rows(
    sql: str,
    params: tuple[Any, ...] = (),
) -> list[sqlite3.Row]:
    """Executa uma query SELECT e retorna todas as linhas."""
    if not db_exists():
        return []
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        return conn.execute(sql, params).fetchall()


def get_connection() -> sqlite3.Connection | None:
    """Retorna uma conexão SQLite ou None se o DB não existir."""
    if not db_exists():
        return None
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


# ── Tabelas de Topologia ──────────────────────────────────────────────────────

def ensure_topology_tables() -> None:
    """
    Cria as tabelas de topologia (nós, ARP, MAC, LLDP) caso não existam.

    Segue o mesmo padrão de ``CREATE TABLE IF NOT EXISTS`` usado pelos demais
    repositórios do projeto (sem sistema de migração formal).
    """
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        conn.executescript(
            """
            -- Nós de rede correlacionados (visão unificada L2/L3)
            CREATE TABLE IF NOT EXISTS topology_nodes (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_id    TEXT    NOT NULL,
                device_id      TEXT    NOT NULL,
                mac_address    TEXT    NOT NULL,
                ip_address     TEXT,
                hostname       TEXT,
                vlan_id        INTEGER,
                switch_port    TEXT,
                vendor_oui     TEXT,
                first_seen     TEXT    NOT NULL DEFAULT (datetime('now')),
                last_seen      TEXT    NOT NULL DEFAULT (datetime('now')),
                authorized     INTEGER NOT NULL DEFAULT 0,
                UNIQUE(customer_id, mac_address)
            );

            CREATE INDEX IF NOT EXISTS idx_topo_nodes_vlan
                ON topology_nodes(vlan_id);
            CREATE INDEX IF NOT EXISTS idx_topo_nodes_customer
                ON topology_nodes(customer_id);
            CREATE INDEX IF NOT EXISTS idx_topo_nodes_last_seen
                ON topology_nodes(last_seen);

            -- Tabela ARP (L3: IP ↔ MAC)
            CREATE TABLE IF NOT EXISTS topology_arp (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_id    TEXT    NOT NULL,
                device_id      TEXT    NOT NULL,
                ip_address     TEXT    NOT NULL,
                mac_address    TEXT    NOT NULL,
                interface      TEXT,
                vlan_id        INTEGER,
                collected_at   TEXT    NOT NULL DEFAULT (datetime('now'))
            );

            CREATE INDEX IF NOT EXISTS idx_topo_arp_customer
                ON topology_arp(customer_id, mac_address);

            -- Tabela MAC / Bridge Host (L2: MAC → porta → VLAN)
            CREATE TABLE IF NOT EXISTS topology_mac (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_id    TEXT    NOT NULL,
                device_id      TEXT    NOT NULL,
                mac_address    TEXT    NOT NULL,
                interface      TEXT,
                vlan_id        INTEGER,
                switch_port    TEXT,
                vendor_oui     TEXT,
                is_local       INTEGER NOT NULL DEFAULT 0,
                collected_at   TEXT    NOT NULL DEFAULT (datetime('now'))
            );

            CREATE INDEX IF NOT EXISTS idx_topo_mac_customer
                ON topology_mac(customer_id, mac_address);

            -- Vizinhos LLDP / CDP / Neighbor Discovery
            CREATE TABLE IF NOT EXISTS topology_lldp (
                id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_id         TEXT    NOT NULL,
                device_id           TEXT    NOT NULL,
                local_port          TEXT,
                remote_device       TEXT,
                remote_port         TEXT,
                remote_ip           TEXT,
                remote_mac          TEXT,
                remote_platform     TEXT,
                remote_description  TEXT,
                collected_at        TEXT    NOT NULL DEFAULT (datetime('now'))
            );

            CREATE INDEX IF NOT EXISTS idx_topo_lldp_customer
                ON topology_lldp(customer_id, device_id);
            """
        )
        conn.commit()
