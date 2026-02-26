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
import time
from typing import Any, Generator

from flask import Blueprint, Response, jsonify, render_template, request, stream_with_context

from dashboard.common.constants import (
    OPEN_INCIDENT_STATUSES,
    SSE_DEFAULT_SECONDS,
    SSE_MAX_SECONDS,
    SSE_MIN_SECONDS,
)
from dashboard.common.db import query_rows
from dashboard.common.http import wants_json
from inventory.customer.customer import DEVICE_INVENTORY

health_bp = Blueprint("health", __name__)

def _get_overview_data() -> dict[str, Any]:
    """
    Monta os KPIs consolidados consultando o SQLite e o DEVICE_INVENTORY.

    Fontes:
      - DEVICE_INVENTORY  → total_devices (fonte de verdade do inventário)
      - tabela incidents  → contagens de incidentes abertos por severidade,
                            dispositivos com incidente aberto, últimos 5
    """
    # ── 1. Contagem de incidentes abertos por severidade ──────────────────
    placeholders = ",".join("?" * len(OPEN_INCIDENT_STATUSES))
    severity_rows = query_rows(
        f"""
        SELECT UPPER(severity) AS sev, COUNT(*) AS cnt
        FROM   incidents
        WHERE  status IN ({placeholders})
        GROUP  BY UPPER(severity)
        """,
        tuple(OPEN_INCIDENT_STATUSES),
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
        rows = query_rows(
            f"""
            SELECT DISTINCT device_id
            FROM   incidents
            WHERE  status IN ({placeholders})
            """,
            tuple(OPEN_INCIDENT_STATUSES),
        )
        devices_with_incident = {r["device_id"] for r in rows}

    total_devices = len(DEVICE_INVENTORY)
    with_incident  = len(devices_with_incident)
    healthy        = total_devices - with_incident

    # ── 3. Últimos 5 incidentes abertos ──────────────────────────────────
    recent_rows = query_rows(
        f"""
        SELECT id, timestamp, customer_id, device_id, severity, category, status
        FROM   incidents
        WHERE  status IN ({placeholders})
        ORDER  BY timestamp DESC
        LIMIT  5
        """,
        tuple(OPEN_INCIDENT_STATUSES),
    )
    recent_incidents = [dict(r) for r in recent_rows]

    # ── 4. Remediações (placeholder — sem tabela dedicada ainda) ──────────
    approved_rows = query_rows(
        "SELECT COUNT(*) AS cnt FROM incidents WHERE status = 'aprovado'"
    )
    executed_rows = query_rows(
        """
        SELECT COUNT(*) AS cnt FROM incidents
        WHERE  status = 'validado'
          AND  date(timestamp) = date('now')
        """
    )
    failed_rows = query_rows(
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

    if wants_json(request):
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
        interval = int(request.args.get("interval", SSE_DEFAULT_SECONDS))
    except (TypeError, ValueError):
        interval = SSE_DEFAULT_SECONDS

    interval = max(SSE_MIN_SECONDS, min(SSE_MAX_SECONDS, interval))

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

