"""
dashboard/blueprints/incidents.py
Blueprint de gerenciamento de incidentes (drift e falhas).

Endpoints:
    GET  /incidents                — lista com filtros + paginação
    GET  /incidents/<int:id>       — detalhe completo + diff estruturado
"""

from __future__ import annotations

from flask import Blueprint, jsonify, render_template, request

from dashboard.common.http import wants_json
from dashboard.repositories.incidents_repository import (
    get_incident as repo_get_incident,
    list_incidents as repo_list_incidents,
)

incidents_bp = Blueprint("incidents", __name__)


# ── Rotas ──────────────────────────────────────────────────────────────────────


@incidents_bp.get("/")
def list_incidents():
    """
    Lista incidentes com filtros por cliente, severidade e status.
    Retorna HTML para navegador ou JSON para clientes de API.
    """
    customer = request.args.get("customer")
    severity = request.args.get("severity")
    status   = request.args.get("status")
    page     = max(1, int(request.args.get("page", 1)))

    incidents, total = repo_list_incidents(
        customer=customer,
        severity=severity,
        status=status,
        page=page,
    )

    if wants_json(request):
        return jsonify({"incidents": incidents, "total": total, "page": page})

    return render_template(
        "incidents.html",
        incidents=incidents,
        total=total,
        page=page,
        filters={"customer": customer, "severity": severity, "status": status},
    )


@incidents_bp.get("/<int:incident_id>")
def get_incident(incident_id: int):
    """Detalhe do incidente: diff estruturado, metadados e severidade."""
    incident = repo_get_incident(incident_id)

    if incident is None:
        if wants_json(request):
            return jsonify({"error": f"Incidente '{incident_id}' não encontrado."}), 404
        return render_template("404.html"), 404

    if wants_json(request):
        return jsonify(incident)

    return render_template("incident_detail.html", incident=incident)
