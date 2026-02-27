"""
api/blueprints/health.py
Blueprint de saúde geral do ambiente monitorado.

Endpoints:
    GET /health/overview     — KPIs (HTML ou JSON)
    GET /health/api/overview — KPIs JSON puro (polling JS)
    GET /health/stream       — SSE com KPIs em tempo real
    GET /health/ping         — liveness check
"""

from __future__ import annotations

import json
import time
from typing import Generator

from flask import (
    Blueprint,
    Response,
    jsonify,
    render_template,
    request,
    stream_with_context,
)

from api.http_utils import wants_json
from core.services.overview_service import get_overview_data

health_bp = Blueprint("health", __name__)

# ── Constantes SSE (escopo web) ──────────────────────
SSE_MIN_SECONDS: int = 5
SSE_MAX_SECONDS: int = 300
SSE_DEFAULT_SECONDS: int = 30


# ── SSE Generator ────────────────────────────────────


def _sse_generator(
    interval: int,
) -> Generator[str, None, None]:
    """Eventos SSE com KPIs a cada *interval* s."""
    yield "retry: 5000\n\n"
    while True:
        try:
            data = get_overview_data()
            payload = json.dumps(data, default=str)
            yield f"data: {payload}\n\n"
            yield ": heartbeat\n\n"
        except Exception:  # noqa: BLE001
            yield "data: {}\n\n"
            yield ": heartbeat\n\n"
        time.sleep(interval)


# ── Rotas ────────────────────────────────────────────


@health_bp.get("/overview")
def overview():
    """Painel executivo com KPIs (HTML ou JSON)."""
    data = get_overview_data()

    if wants_json(request):
        return jsonify(data)

    return render_template(
        "overview.html", overview=data
    )


@health_bp.get("/api/overview")
def api_overview():
    """JSON puro — fallback de polling JS."""
    return jsonify(get_overview_data())


@health_bp.get("/stream")
def stream():
    """SSE: KPIs atualizados periodicamente.

    Query params:
        interval (int): segundos entre eventos.
            Padrão 30, min 5, max 300.
    """
    try:
        interval = int(
            request.args.get(
                "interval", SSE_DEFAULT_SECONDS
            )
        )
    except (TypeError, ValueError):
        interval = SSE_DEFAULT_SECONDS

    interval = max(
        SSE_MIN_SECONDS,
        min(SSE_MAX_SECONDS, interval),
    )

    return Response(
        stream_with_context(
            _sse_generator(interval)
        ),
        content_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


@health_bp.get("/ping")
def ping():
    """Liveness check da aplicação."""
    return jsonify({"status": "ok"})
