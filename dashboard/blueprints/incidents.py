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
    list_distinct_severities as repo_list_distinct_severities,
    list_distinct_statuses as repo_list_distinct_statuses,
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
    device_id = request.args.get("device_id")
    vendor = request.args.get("vendor")
    severity = request.args.get("severity")
    min_severity = request.args.get("min_severity")
    status   = request.args.get("status")
    start_date = request.args.get("start_date")
    end_date = request.args.get("end_date")
    sort = request.args.get("sort", "newest")
    try:
        page = max(1, int(request.args.get("page", 1)))
    except (TypeError, ValueError):
        page = 1
    page_size = 25

    incidents, total = repo_list_incidents(
        customer=customer,
        device_id=device_id,
        vendor=vendor,
        severity=severity,
        min_severity=min_severity,
        status=status,
        start_date=start_date,
        end_date=end_date,
        sort=sort,
        page=page,
        page_size=page_size,
    )

    has_next = (page * page_size) < total
    has_prev = page > 1
    base_query = {
        "customer": customer or "",
        "device_id": device_id or "",
        "vendor": vendor or "",
        "severity": severity or "",
        "min_severity": min_severity or "",
        "status": status or "",
        "start_date": start_date or "",
        "end_date": end_date or "",
        "sort": sort or "newest",
    }

    if wants_json(request):
        return jsonify(
            {
                "incidents": incidents,
                "total": total,
                "page": page,
                "page_size": page_size,
                "has_next": has_next,
                "has_prev": has_prev,
                "sort": sort,
            }
        )

    severity_options = repo_list_distinct_severities() or [
        "CRITICAL", "HIGH", "WARNING", "INFO"
    ]
    status_values = repo_list_distinct_statuses() or ["new", "em_analise", "aprovado", "executado", "validado", "falhou"]
    status_label_map = {
        "new": "Novo",
        "novo": "Novo",
        "em_analise": "Em análise",
        "aprovado": "Aprovado",
        "executado": "Executado",
        "validado": "Validado",
        "falhou": "Falhou",
        "revertido": "Revertido",
    }
    status_options = [
        {"value": value, "label": status_label_map.get(value, value.replace("_", " ").title())}
        for value in status_values
    ]

    return render_template(
        "incidents.html",
        incidents=incidents,
        total=total,
        page=page,
        has_next=has_next,
        has_prev=has_prev,
        page_size=page_size,
        base_query=base_query,
        severity_options=severity_options,
        status_options=status_options,
        filters={
            "customer": customer,
            "device_id": device_id,
            "vendor": vendor,
            "severity": severity,
            "min_severity": min_severity,
            "status": status,
            "start_date": start_date,
            "end_date": end_date,
            "sort": sort,
        },
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
