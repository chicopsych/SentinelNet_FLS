from __future__ import annotations

import sqlite3
from typing import Any

from dashboard.common.constants import DB_PATH


def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def ensure_inventory_table() -> None:
    with _connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS inventory_devices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_id TEXT NOT NULL,
                device_id TEXT NOT NULL,
                vendor TEXT NOT NULL,
                host TEXT NOT NULL,
                port INTEGER NOT NULL,
                active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(customer_id, device_id),
                UNIQUE(host, port)
            )
            """
        )
        conn.commit()


def list_inventory_devices() -> list[dict[str, Any]]:
    ensure_inventory_table()
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT customer_id, device_id, vendor, host, port, active, created_at
            FROM inventory_devices
            ORDER BY customer_id, device_id
            """
        ).fetchall()
    return [dict(row) for row in rows]


def create_inventory_device(
    *,
    customer_id: str,
    device_id: str,
    vendor: str,
    host: str,
    port: int,
) -> tuple[bool, str]:
    ensure_inventory_table()

    if not customer_id.strip() or not device_id.strip() or not vendor.strip() or not host.strip():
        return False, "Preencha todos os campos obrigatórios."

    if port <= 0 or port > 65535:
        return False, "Porta inválida. Informe um valor entre 1 e 65535."

    with _connect() as conn:
        by_device = conn.execute(
            """
            SELECT 1 FROM inventory_devices
            WHERE customer_id = ? AND device_id = ?
            LIMIT 1
            """,
            (customer_id, device_id),
        ).fetchone()
        if by_device:
            return False, "Dispositivo já cadastrado para este cliente."

        by_host = conn.execute(
            """
            SELECT 1 FROM inventory_devices
            WHERE host = ? AND port = ?
            LIMIT 1
            """,
            (host, port),
        ).fetchone()
        if by_host:
            return False, "Já existe dispositivo cadastrado com este host/porta."

        conn.execute(
            """
            INSERT INTO inventory_devices (customer_id, device_id, vendor, host, port)
            VALUES (?, ?, ?, ?, ?)
            """,
            (customer_id, device_id, vendor, host, port),
        )
        conn.commit()

    return True, "Dispositivo cadastrado com sucesso."


def delete_inventory_device(*, customer_id: str, device_id: str) -> None:
    ensure_inventory_table()
    with _connect() as conn:
        conn.execute(
            """
            DELETE FROM inventory_devices
            WHERE customer_id = ? AND device_id = ?
            """,
            (customer_id, device_id),
        )
        conn.commit()
