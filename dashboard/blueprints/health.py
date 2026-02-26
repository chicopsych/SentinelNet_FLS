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

from dashboard.common.constants import SSE_DEFAULT_SECONDS, SSE_MAX_SECONDS, SSE_MIN_SECONDS
from dashboard.common.http import wants_json
from dashboard.repositories.incidents_repository import (
    count_by_status,
    count_open_by_severity,
    count_validated_today,
    list_distinct_open_devices,
    list_recent_open,
)
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
    severity_counts = count_open_by_severity()
    total_open = sum(severity_counts.values())

    # ── 2. Dispositivos do inventário com ≥1 incidente aberto ────────────
    devices_with_incident = list_distinct_open_devices() if total_open > 0 else set()

    total_devices = len(DEVICE_INVENTORY)
    with_incident  = len(devices_with_incident)
    healthy        = total_devices - with_incident

    # ── 3. Últimos 5 incidentes abertos ──────────────────────────────────
    recent_incidents = list_recent_open(limit=5)

    # ── 4. Remediações (placeholder — sem tabela dedicada ainda) ──────────
    pending_approval = count_by_status("aprovado")
    executed_today = count_validated_today()
    failed = count_by_status("falhou")

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
            "pending_approval": pending_approval,
            "executed_today": executed_today,
            "failed": failed,
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
    yield "retry: 5000\n\n"
    while True:
        try:
            data = _get_overview_data()
            payload = json.dumps(data, default=str)
            yield f"data: {payload}\n\n"
            yield ": heartbeat\n\n"
        except Exception:  # noqa: BLE001
            yield "data: {}\n\n"
            yield ": heartbeat\n\n"
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

