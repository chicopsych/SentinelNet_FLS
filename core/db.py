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
