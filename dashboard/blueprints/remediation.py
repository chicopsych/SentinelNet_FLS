"""
dashboard/blueprints/remediation.py
Blueprint de remediação controlada de incidentes.

Endpoints API (token):
    POST  /incidents/<id>/remediation/api/suggest
    POST  /incidents/<id>/remediation/api/approve
    POST  /incidents/<id>/remediation/api/execute
    GET   /incidents/<id>/remediation/api/status

Endpoints UI (form/session):
    POST  /incidents/<id>/remediation/ui/suggest
    POST  /incidents/<id>/remediation/ui/approve
    POST  /incidents/<id>/remediation/ui/execute

Fluxo de estados:
    novo → em_analise → aprovado → executado → validado
                                 ↘ falhou → revertido
"""

from flask import Blueprint, flash, jsonify, redirect, request, url_for

from .auth import token_required

remediation_bp = Blueprint("remediation", __name__)

VALID_STATES = ("novo", "em_analise", "aprovado", "executado", "falhou", "revertido", "validado")


def _to_incident_detail(incident_id: str):
    return redirect(url_for("incidents.get_incident", incident_id=incident_id))


def _suggest_remediation(incident_id: str) -> dict:
    return {
        "incident_id": incident_id,
        "status": "em_analise",
        "commands": [],
        "risk": None,
        "impact": None,
        "requires_approval": True,
        "dry_run_available": True,
    }


def _approve_remediation(incident_id: str, approved_by: str) -> dict:
    return {
        "incident_id": incident_id,
        "status": "aprovado",
        "approved_by": approved_by,
    }


def _execute_remediation(incident_id: str, dry_run: bool = True) -> dict:
    return {
        "incident_id": incident_id,
        "dry_run": dry_run,
        "status": "executado" if not dry_run else "em_analise",
        "result": None,
        "post_snapshot_match": None,
    }


@remediation_bp.post("/<incident_id>/remediation/ui/suggest")
def ui_suggest(incident_id: str):
    _ = _suggest_remediation(incident_id)
    flash("Sugestão de remediação gerada (UI).", "info")
    return _to_incident_detail(incident_id)


@remediation_bp.post("/<incident_id>/remediation/ui/approve")
def ui_approve(incident_id: str):
    approved_by = request.form.get("approved_by", "operator")
    _ = _approve_remediation(incident_id, approved_by)
    flash("Remediação aprovada (UI).", "success")
    return _to_incident_detail(incident_id)


@remediation_bp.post("/<incident_id>/remediation/ui/execute")
def ui_execute(incident_id: str):
    dry_run = str(request.form.get("dry_run", "true")).lower() != "false"
    _ = _execute_remediation(incident_id, dry_run=dry_run)
    if dry_run:
        flash("Dry-run de remediação executado.", "warning")
    else:
        flash("Execução de remediação disparada.", "danger")
    return _to_incident_detail(incident_id)


@remediation_bp.post("/<incident_id>/remediation/api/suggest")
@token_required
def api_suggest(incident_id: str):
    result = _suggest_remediation(incident_id)
    return jsonify(result), 202


@remediation_bp.post("/<incident_id>/remediation/api/approve")
@token_required
def api_approve(incident_id: str):
    body = request.get_json(silent=True) or {}
    approved_by = body.get("approved_by", "system")
    result = _approve_remediation(incident_id, approved_by)
    return jsonify(result), 200


@remediation_bp.post("/<incident_id>/remediation/api/execute")
@token_required
def api_execute(incident_id: str):
    body = request.get_json(silent=True) or {}
    dry_run: bool = body.get("dry_run", True)
    result = _execute_remediation(incident_id, dry_run=dry_run)
    return jsonify(result), 202


@remediation_bp.get("/<incident_id>/remediation/api/status")
@token_required
def api_status(incident_id: str):
    return jsonify({"incident_id": incident_id, "status": "novo", "history": []})
