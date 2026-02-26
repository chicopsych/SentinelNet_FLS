"""
dashboard/blueprints/health.py
Blueprint de saúde geral do ambiente monitorado.

Endpoints:
    GET /health/overview        — KPIs consolidados (HTML ou JSON via Accept)
    GET /health/api/overview    — KPIs em JSON puro (usado pelo polling JS)
    GET /health/stream          — Server-Sent Events com KPIs em tempo real
    GET /health/ping            — liveness check da aplicação
"""

from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from typing import Any, Generator

from flask import Blueprint, Response, jsonify, render_template, request, stream_with_context

from inventory.customer.customer import DEVICE_INVENTORY

health_bp = Blueprint("health", __name__)

# Caminho do banco — mesma referência do IncidentEngine
_DB_PATH = Path(__file__).resolve().parent.parent.parent / "inventory" / "sentinel_data.db"

# Status de incidente considerado "aberto" (não resolvido)
_OPEN_STATUSES = ("new", "em_analise")

# Intervalo SSE: mínimo 5s, máximo 300s, padrão 30s
_SSE_MIN = 5
_SSE_MAX = 300
_SSE_DEFAULT = 30


# ── Queries SQLite ─────────────────────────────────────────────────────────────


def _query_db(sql: str, params: tuple = ()) -> list[sqlite3.Row]:
    """Executa uma SELECT e retorna as linhas, ou [] se o banco não existir."""
    if not _DB_PATH.exists():
        return []
    with sqlite3.connect(_DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        return conn.execute(sql, params).fetchall()


def _get_overview_data() -> dict[str, Any]:
    """
    Monta os KPIs consolidados consultando o SQLite e o DEVICE_INVENTORY.

    Fontes:
      - DEVICE_INVENTORY  → total_devices (fonte de verdade do inventário)
      - tabela incidents  → contagens de incidentes abertos por severidade,
                            dispositivos com incidente aberto, últimos 5
    """
    # ── 1. Contagem de incidentes abertos por severidade ──────────────────
    placeholders = ",".join("?" * len(_OPEN_STATUSES))
    severity_rows = _query_db(
        f"""
        SELECT UPPER(severity) AS sev, COUNT(*) AS cnt
        FROM   incidents
        WHERE  status IN ({placeholders})
        GROUP  BY UPPER(severity)
        """,
        tuple(_OPEN_STATUSES),
    )

    severity_counts: dict[str, int] = {}
    total_open = 0
    for row in severity_rows:
        sev = row["sev"]
        cnt = row["cnt"]
        severity_counts[sev] = cnt
        total_open += cnt

    # ── 2. Dispositivos do inventário com ≥1 incidente aberto ────────────
    devices_with_incident: set[str] = set()
    if total_open > 0:
        rows = _query_db(
            f"""
            SELECT DISTINCT device_id
            FROM   incidents
            WHERE  status IN ({placeholders})
            """,
            tuple(_OPEN_STATUSES),
        )
        devices_with_incident = {r["device_id"] for r in rows}

    total_devices = len(DEVICE_INVENTORY)
    with_incident  = len(devices_with_incident)
    healthy        = total_devices - with_incident

    # ── 3. Últimos 5 incidentes abertos ──────────────────────────────────
    recent_rows = _query_db(
        f"""
        SELECT id, timestamp, customer_id, device_id, severity, category, status
        FROM   incidents
        WHERE  status IN ({placeholders})
        ORDER  BY timestamp DESC
        LIMIT  5
        """,
        tuple(_OPEN_STATUSES),
    )
    recent_incidents = [dict(r) for r in recent_rows]

    # ── 4. Remediações (placeholder — sem tabela dedicada ainda) ──────────
    approved_rows = _query_db(
        "SELECT COUNT(*) AS cnt FROM incidents WHERE status = 'aprovado'"
    )
    executed_rows = _query_db(
        """
        SELECT COUNT(*) AS cnt FROM incidents
        WHERE  status = 'validado'
          AND  date(timestamp) = date('now')
        """
    )
    failed_rows = _query_db(
        "SELECT COUNT(*) AS cnt FROM incidents WHERE status = 'falhou'"
    )

    return {
        "devices": {
            "total":         total_devices,
            "healthy":       max(healthy, 0),
            "with_incident": with_incident,
        },
        "incidents": {
            "open":     total_open,
            "critical": severity_counts.get("CRITICAL", 0),
            "high":     severity_counts.get("HIGH", 0),
            "warning":  severity_counts.get("WARNING", 0),
            "info":     severity_counts.get("INFO", 0),
        },
        "remediation": {
            "pending_approval": approved_rows[0]["cnt"] if approved_rows else 0,
            "executed_today":   executed_rows[0]["cnt"] if executed_rows else 0,
            "failed":           failed_rows[0]["cnt"]   if failed_rows   else 0,
        },
        "slo": {
            "mtta_minutes": None,
            "mttr_minutes": None,
        },
        "recent_incidents": recent_incidents,
    }


# ── SSE Generator ──────────────────────────────────────────────────────────────


def _sse_generator(interval: int) -> Generator[str, None, None]:
    """Gera eventos SSE com os KPIs atualizados a cada `interval` segundos."""
    while True:
        try:
            data = _get_overview_data()
            payload = json.dumps(data, default=str)
            yield f"data: {payload}\n\n"
        except Exception:  # noqa: BLE001
            yield "data: {}\n\n"
        time.sleep(interval)


# ── Rotas ──────────────────────────────────────────────────────────────────────


@health_bp.get("/overview")
def overview():
    """Painel executivo com KPIs. Retorna HTML ou JSON conforme Accept header."""
    data = _get_overview_data()

    if _wants_json():
        return jsonify(data)

    return render_template("overview.html", overview=data)


@health_bp.get("/api/overview")
def api_overview():
    """Endpoint JSON puro — utilizado pelo polling JS como fallback do SSE."""
    return jsonify(_get_overview_data())


@health_bp.get("/stream")
def stream():
    """
    Server-Sent Events: envia KPIs atualizados periodicamente ao browser.

    Query params:
        interval (int): segundos entre eventos. Padrão 30, min 5, max 300.
    """
    try:
        interval = int(request.args.get("interval", _SSE_DEFAULT))
    except (TypeError, ValueError):
        interval = _SSE_DEFAULT

    interval = max(_SSE_MIN, min(_SSE_MAX, interval))

    return Response(
        stream_with_context(_sse_generator(interval)),
        content_type="text/event-stream",
        headers={
            "Cache-Control":    "no-cache",
            "X-Accel-Buffering": "no",
            "Connection":       "keep-alive",
        },
    )


@health_bp.get("/ping")
def ping():
    """Liveness check da aplicação."""
    return jsonify({"status": "ok"})


# ── Utilitários ───────────────────────────────────────────────────────────────


def _wants_json() -> bool:
    best = request.accept_mimetypes.best_match(["application/json", "text/html"])
    return best == "application/json"
