"""
dashboard/blueprints/incidents.py
Blueprint de gerenciamento de incidentes (drift e falhas).

Endpoints:
    GET  /incidents                — lista com filtros
    GET  /incidents/<id>           — detalhe + evidência técnica
"""

from flask import Blueprint, jsonify, render_template, request

incidents_bp = Blueprint("incidents", __name__)


# ── Helpers ────────────────────────────────────────────────────────────────────


def _list_incidents(
    customer: str | None = None,
    severity: str | None = None,
    status: str | None = None,
    vendor: str | None = None,
    page: int = 1,
    page_size: int = 25,
) -> tuple[list[dict], int]:
    """
    Retorna (lista de incidentes, total).
    TODO: integrar com IncidentRepository e aplicar filtros/paginação reais.
    """
    return [], 0


def _get_incident(incident_id: str) -> dict | None:
    """
    Retorna incidente completo com diff e evidências.
    TODO: integrar com IncidentRepository.
    """
    return None


# ── Rotas ──────────────────────────────────────────────────────────────────────


@incidents_bp.get("/")
def list_incidents():
    """
    Lista incidentes com filtros por cliente, severidade, status, vendor e período.
    Retorna HTML para navegador ou JSON para clientes de API.
    """
    customer = request.args.get("customer")
    severity = request.args.get("severity")
    status   = request.args.get("status")
    vendor   = request.args.get("vendor")
    page     = int(request.args.get("page", 1))

    incidents, total = _list_incidents(
        customer=customer,
        severity=severity,
        status=status,
        vendor=vendor,
        page=page,
    )

    if _wants_json():
        return jsonify({"incidents": incidents, "total": total, "page": page})

    return render_template(
        "incidents.html",
        incidents=incidents,
        total=total,
        page=page,
        filters={"customer": customer, "severity": severity, "status": status},
    )


@incidents_bp.get("/<incident_id>")
def get_incident(incident_id: str):
    """Detalhe do incidente: diff, evidência técnica, histórico de ações e remediação."""
    incident = _get_incident(incident_id)

    if incident is None:
        if _wants_json():
            return jsonify({"error": f"Incidente '{incident_id}' não encontrado."}), 404
        return render_template("404.html"), 404

    if _wants_json():
        return jsonify(incident)

    return render_template("incident_detail.html", incident=incident)


# ── Utilitários ───────────────────────────────────────────────────────────────


def _wants_json() -> bool:
    best = request.accept_mimetypes.best_match(["application/json", "text/html"])
    return best == "application/json"
