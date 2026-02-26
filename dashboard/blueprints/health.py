"""
dashboard/blueprints/health.py
Blueprint de saúde geral do ambiente monitorado.

Endpoints:
    GET /health/overview  — KPIs consolidados (saudável x incidente, por severidade)
    GET /health/ping      — liveness check da aplicação
"""

from flask import Blueprint, jsonify, render_template

health_bp = Blueprint("health", __name__)


# ── Helpers (substituir por consulta real ao repositório de incidentes) ────────


def _get_overview_data() -> dict:
    """Retorna estrutura de KPIs consolidados. Dados reais virão do IncidentRepository."""
    return {
        "devices": {
            "total": 0,
            "healthy": 0,
            "with_incident": 0,
        },
        "incidents": {
            "open": 0,
            "critical": 0,
            "warning": 0,
            "info": 0,
        },
        "remediation": {
            "pending_approval": 0,
            "executed_today": 0,
            "failed": 0,
        },
        "slo": {
            "mtta_minutes": None,
            "mttr_minutes": None,
        },
    }


# ── Rotas ─────────────────────────────────────────────────────────────────────


@health_bp.get("/overview")
def overview():
    """Painel executivo com KPIs. Retorna HTML ou JSON conforme Accept header."""
    data = _get_overview_data()

    if _wants_json():
        return jsonify(data)

    return render_template("overview.html", overview=data)


@health_bp.get("/ping")
def ping():
    """Liveness check da aplicação."""
    return jsonify({"status": "ok"})


# ── Utilitários ───────────────────────────────────────────────────────────────


def _wants_json() -> bool:
    from flask import request

    best = request.accept_mimetypes.best_match(["application/json", "text/html"])
    return best == "application/json"
