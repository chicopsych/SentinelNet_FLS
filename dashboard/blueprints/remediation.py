"""
dashboard/blueprints/remediation.py
Blueprint de remediação controlada de incidentes.

Endpoints (todos sob /incidents/<id>/remediation/):
    POST  /incidents/<id>/remediation/suggest   — gera sugestão de correção
    POST  /incidents/<id>/remediation/approve   — aprova sugestão pendente
    POST  /incidents/<id>/remediation/execute   — executa remediação aprovada
    GET   /incidents/<id>/remediation/status    — estado atual do pipeline

Fluxo de estados:
    novo → em_analise → aprovado → executado → validado
                                 ↘ falhou → revertido
"""

from flask import Blueprint, jsonify, request

from .auth import token_required

remediation_bp = Blueprint("remediation", __name__)


# ── Estados válidos do pipeline ────────────────────────────────────────────────

VALID_STATES = ("novo", "em_analise", "aprovado", "executado", "falhou", "revertido", "validado")


# ── Helpers ────────────────────────────────────────────────────────────────────


def _suggest_remediation(incident_id: str) -> dict:
    """
    Gera sugestão de comandos corretivos para o incidente.
    TODO: integrar com RemediationService (rule-based + IA opcional).
    """
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
    """
    Registra aprovação da sugestão. Apenas incidentes em `em_analise` podem ser aprovados.
    TODO: integrar com IncidentRepository e trilha de auditoria.
    """
    return {
        "incident_id": incident_id,
        "status": "aprovado",
        "approved_by": approved_by,
    }


def _execute_remediation(incident_id: str, dry_run: bool = True) -> dict:
    """
    Executa (ou simula) os comandos corretivos aprovados.
    TODO: integrar com RemediationService e recoletar snapshot pós-execução.
    """
    return {
        "incident_id": incident_id,
        "dry_run": dry_run,
        "status": "executado" if not dry_run else "em_analise",
        "result": None,
        "post_snapshot_match": None,
    }


# ── Rotas ──────────────────────────────────────────────────────────────────────


@remediation_bp.post("/<incident_id>/remediation/suggest")
@token_required
def suggest(incident_id: str):
    """Gera sugestão de remediação para o incidente informado."""
    result = _suggest_remediation(incident_id)
    return jsonify(result), 202


@remediation_bp.post("/<incident_id>/remediation/approve")
@token_required
def approve(incident_id: str):
    """Registra aprovação da sugestão pendente. Requer campo `approved_by` no body."""
    body = request.get_json(silent=True) or {}
    approved_by = body.get("approved_by", "system")
    result = _approve_remediation(incident_id, approved_by)
    return jsonify(result), 200


@remediation_bp.post("/<incident_id>/remediation/execute")
@token_required
def execute(incident_id: str):
    """
    Executa a remediação aprovada.
    Por padrão opera em modo dry-run. Passe `{"dry_run": false}` para execução real.
    """
    body = request.get_json(silent=True) or {}
    dry_run: bool = body.get("dry_run", True)
    result = _execute_remediation(incident_id, dry_run=dry_run)
    return jsonify(result), 202


@remediation_bp.get("/<incident_id>/remediation/status")
@token_required
def status(incident_id: str):
    """Retorna o estado atual do pipeline de remediação para o incidente."""
    # TODO: consultar IncidentRepository para estado real
    return jsonify({"incident_id": incident_id, "status": "novo", "history": []})
