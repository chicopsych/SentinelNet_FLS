from __future__ import annotations

import sqlite3
from typing import Any

from .constants import DB_PATH


def db_exists() -> bool:
    return DB_PATH.exists()


def query_rows(sql: str, params: tuple[Any, ...] = ()) -> list[sqlite3.Row]:
    if not db_exists():
        return []
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        return conn.execute(sql, params).fetchall()


def get_connection() -> sqlite3.Connection | None:
    if not db_exists():
        return None
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn
