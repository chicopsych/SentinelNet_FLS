"""
api/blueprints/remediation.py
Blueprint de remediação controlada de incidentes.

Endpoints API (token):
    POST  /incidents/<id>/remediation/api/suggest
    POST  /incidents/<id>/remediation/api/approve
    POST  /incidents/<id>/remediation/api/execute
    GET   /incidents/<id>/remediation/api/status

Endpoints UI (form):
    POST  /incidents/<id>/remediation/ui/suggest
    POST  /incidents/<id>/remediation/ui/approve
    POST  /incidents/<id>/remediation/ui/execute
"""

from flask import (
    Blueprint,
    flash,
    jsonify,
    redirect,
    request,
    url_for,
)

from api.blueprints.auth import token_required
from core.services.remediation_service import (
    approve,
    execute,
    suggest,
)

remediation_bp = Blueprint("remediation", __name__)


def _to_incident_detail(incident_id: str):
    return redirect(
        url_for(
            "incidents.get_incident",
            incident_id=incident_id,
        )
    )


# ── UI routes ────────────────────────────────────────


@remediation_bp.post(
    "/<incident_id>/remediation/ui/suggest"
)
def ui_suggest(incident_id: str):
    _ = suggest(incident_id)
    flash(
        "Sugestão de remediação gerada (UI).",
        "info",
    )
    return _to_incident_detail(incident_id)


@remediation_bp.post(
    "/<incident_id>/remediation/ui/approve"
)
def ui_approve(incident_id: str):
    approved_by = request.form.get(
        "approved_by", "operator"
    )
    _ = approve(incident_id, approved_by)
    flash("Remediação aprovada (UI).", "success")
    return _to_incident_detail(incident_id)


@remediation_bp.post(
    "/<incident_id>/remediation/ui/execute"
)
def ui_execute(incident_id: str):
    dry_run = (
        str(
            request.form.get("dry_run", "true")
        ).lower()
        != "false"
    )
    _ = execute(incident_id, dry_run=dry_run)
    if dry_run:
        flash(
            "Dry-run de remediação executado.",
            "warning",
        )
    else:
        flash(
            "Execução de remediação disparada.",
            "danger",
        )
    return _to_incident_detail(incident_id)


# ── API routes (token) ──────────────────────────────


@remediation_bp.post(
    "/<incident_id>/remediation/api/suggest"
)
@token_required
def api_suggest(incident_id: str):
    return jsonify(suggest(incident_id)), 202


@remediation_bp.post(
    "/<incident_id>/remediation/api/approve"
)
@token_required
def api_approve(incident_id: str):
    body = request.get_json(silent=True) or {}
    approved_by = body.get(
        "approved_by", "system"
    )
    return (
        jsonify(approve(incident_id, approved_by)),
        200,
    )


@remediation_bp.post(
    "/<incident_id>/remediation/api/execute"
)
@token_required
def api_execute(incident_id: str):
    body = request.get_json(silent=True) or {}
    dry_run: bool = body.get("dry_run", True)
    return (
        jsonify(
            execute(incident_id, dry_run=dry_run)
        ),
        202,
    )


@remediation_bp.get(
    "/<incident_id>/remediation/api/status"
)
@token_required
def api_status(incident_id: str):
    return jsonify(
        {
            "incident_id": incident_id,
            "status": "novo",
            "history": [],
        }
    )
