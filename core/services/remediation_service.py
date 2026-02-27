"""
core/services/remediation_service.py
Fluxo de remediação controlada de incidentes.

Stubs que serão implementados quando os drivers
suportarem push de configuração.

Fluxo de estados:
    novo → em_analise → aprovado → executado → validado
                                 ↘ falhou → revertido
"""

from __future__ import annotations

VALID_STATES: tuple[str, ...] = (
    "novo",
    "em_analise",
    "aprovado",
    "executado",
    "falhou",
    "revertido",
    "validado",
)


def suggest(incident_id: str) -> dict[str, object]:
    """Gera sugestão de remediação para um incidente."""
    return {
        "incident_id": incident_id,
        "status": "em_analise",
        "commands": [],
        "risk": None,
        "impact": None,
        "requires_approval": True,
        "dry_run_available": True,
    }


def approve(
    incident_id: str, approved_by: str
) -> dict[str, object]:
    """Registra aprovação de um plano de remediação."""
    return {
        "incident_id": incident_id,
        "status": "aprovado",
        "approved_by": approved_by,
    }


def execute(
    incident_id: str, dry_run: bool = True
) -> dict[str, object]:
    """Executa (ou simula) a remediação aprovada."""
    return {
        "incident_id": incident_id,
        "dry_run": dry_run,
        "status": (
            "executado" if not dry_run else "em_analise"
        ),
        "result": None,
        "post_snapshot_match": None,
    }
