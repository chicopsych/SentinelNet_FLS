"""
core/audit_report.py
────────────────────
Modelo de Relatório de Auditoria e classificação automática de severidade.

Encapsula o resultado do Diff Engine (``DiffReport``) com metadados de
contexto operacional (cliente, dispositivo, timestamps) e calcula um
nível de severidade global para priorização de ações corretivas.

Design Decisions
────────────────
1. ``Severity`` como IntEnum ordenável:
   Permite comparações diretas (``Severity.HIGH > Severity.LOW``) e
   classificação ``max()`` sobre múltiplos critérios, simplificando a
   função ``classify_severity()``.

2. Classificação por pior cenário (*worst-case*):
   A severidade global é determinada pelo tipo de drift mais grave
   detectado, seguindo a hierarquia::

       CRITICAL > HIGH > MEDIUM > LOW > COMPLIANT

   Isso garante que uma única regra de firewall com Position Drift
   (risco de Shadowing) eleve o relatório inteiro para CRITICAL,
   mesmo que os demais campos estejam em conformidade.

3. ``AuditReport`` como Pydantic BaseModel:
   Permite serialização/desserialização nativa via ``model_dump()`` /
   ``model_validate()``, integração direta com JSON e coerência com
   os demais modelos do projeto (``DeviceConfig``, ``Interface``, etc.).

4. ``audit_id`` com UUID v4:
   Identificador único e imutável por relatório, gerado automaticamente.
   Útil para rastreabilidade em banco de dados e correlação de logs.

Hierarquia de Severidade
────────────────────────
- **COMPLIANT** (0): Nenhum drift detectado. Equipamento em conformidade.
- **LOW**       (1): Apenas campos escalares alterados (ex: versão de OS).
- **MEDIUM**    (2): Alterações em listas (interfaces/routes adicionadas,
                     removidas ou modificadas) ou Parameter Drift em firewall.
- **HIGH**      (3): Regras de firewall ausentes ou não documentadas
                     (missing_rules / extra_rules).
- **CRITICAL**  (4): Position Drift em firewall — risco de Shadowing.
                     Requer ação imediata.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import IntEnum
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field

from core.diff_engine import DiffReport


# ─── Enum: Nível de Severidade ────────────────────────────────────────────────

class Severity(IntEnum):
    """
    Nível de severidade do relatório de auditoria.

    IntEnum permite ordenação natural: ``Severity.CRITICAL > Severity.LOW``.
    """

    COMPLIANT = 0
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4

    @property
    def label(self) -> str:
        """Rótulo legível para exibição em relatórios."""
        return self.name

    @property
    def emoji(self) -> str:
        """Ícone visual para relatórios HTML."""
        _map = {0: "✅", 1: "🔵", 2: "🟡", 3: "🟠", 4: "🔴"}
        return _map[self.value]


# ─── Classificação de Severidade ──────────────────────────────────────────────

def classify_severity(report: DiffReport) -> Severity:
    """
    Calcula o nível de severidade global com base nos drifts detectados.

    A severidade é determinada pelo tipo de drift mais grave presente
    no ``DiffReport``, seguindo a hierarquia worst-case.

    Args:
        report: Resultado da comparação Baseline × Current.

    Returns:
        O nível ``Severity`` correspondente ao pior drift encontrado.
    """
    if not report.has_drift:
        return Severity.COMPLIANT

    level = Severity.COMPLIANT

    # ── Escalares alterados → LOW ─────────────────────────────────────────
    scalar_keys = {
        k for k in report.modified
        if not isinstance(report.modified[k], list)
    }
    if scalar_keys or report.added or report.removed:
        # Verificar se added/removed são apenas escalares
        has_scalar_added = any(
            not isinstance(v, list) for v in report.added.values()
        ) if report.added else False
        has_scalar_removed = any(
            not isinstance(v, list) for v in report.removed.values()
        ) if report.removed else False

        if scalar_keys or has_scalar_added or has_scalar_removed:
            level = max(level, Severity.LOW)

    # ── Listas (interfaces, routes) alteradas → MEDIUM ────────────────────
    list_modified = any(
        isinstance(v, list) for v in report.modified.values()
    )
    list_added = any(
        isinstance(v, list) for v in report.added.values()
    )
    list_removed = any(
        isinstance(v, list) for v in report.removed.values()
    )
    if list_modified or list_added or list_removed:
        level = max(level, Severity.MEDIUM)

    # ── Firewall: Parameter Drift → MEDIUM ────────────────────────────────
    if report.firewall_audit.get("parameter_drift"):
        level = max(level, Severity.MEDIUM)

    # ── Firewall: Missing / Extra Rules → HIGH ───────────────────────────
    if (
        report.firewall_audit.get("missing_rules")
        or report.firewall_audit.get("extra_rules")
    ):
        level = max(level, Severity.HIGH)

    # ── Firewall: Position Drift → CRITICAL ──────────────────────────────
    if report.firewall_audit.get("position_drift"):
        level = max(level, Severity.CRITICAL)

    return level


# ─── Modelo: Relatório de Auditoria ──────────────────────────────────────────

class AuditReport(BaseModel):
    """
    Relatório de auditoria completo com metadados operacionais e drift
    classification.

    Encapsula o ``DiffReport`` produzido pelo Diff Engine com informações
    de contexto necessárias para rastreabilidade, histórico e entrega
    ao cliente.
    """

    model_config = ConfigDict(
        str_strip_whitespace=True,
        arbitrary_types_allowed=True,
    )

    # ── Identificação ─────────────────────────────────────────────────────────
    audit_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Identificador único do relatório (UUID v4).",
    )
    customer_id: str = Field(
        ...,
        description=(
            "Identificador do cliente ao qual o dispositivo pertence "
            "(ex: 'cliente_a', 'acme_corp')."
        ),
    )
    device_id: str = Field(
        ...,
        description=(
            "Identificador lógico do dispositivo auditado "
            "(ex: 'borda-01', 'sw-core-01')."
        ),
    )
    hostname: str = Field(
        ...,
        description="Hostname real coletado do dispositivo.",
    )

    # ── Timestamps ────────────────────────────────────────────────────────────
    audit_timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Data/hora de geração do relatório (UTC).",
    )
    baseline_collected_at: Optional[datetime] = Field(
        default=None,
        description="Data/hora de coleta da baseline (se disponível).",
    )
    current_collected_at: Optional[datetime] = Field(
        default=None,
        description="Data/hora de coleta do estado atual (se disponível).",
    )

    # ── Classificação ─────────────────────────────────────────────────────────
    severity: Severity = Field(
        ...,
        description="Nível de severidade calculado automaticamente.",
    )
    severity_label: str = Field(
        default="",
        description="Rótulo legível da severidade (preenchido automaticamente).",
    )

    # ── Dados de Drift ────────────────────────────────────────────────────────
    drift_summary: str = Field(
        default="",
        description="Resumo em uma linha (ex: 'added=1, removed=2, ...').",
    )
    drift_data: dict[str, Any] = Field(
        default_factory=dict,
        description="Conteúdo completo do DiffReport serializado.",
    )

    # ── Factory ───────────────────────────────────────────────────────────────

    @classmethod
    def from_diff_report(
        cls,
        report: DiffReport,
        customer_id: str,
        device_id: str,
        hostname: str,
        baseline_collected_at: Optional[datetime] = None,
        current_collected_at: Optional[datetime] = None,
    ) -> AuditReport:
        """
        Cria um ``AuditReport`` a partir de um ``DiffReport`` do Diff Engine.

        Calcula automaticamente a severidade e preenche os campos derivados.

        Args:
            report: Resultado da comparação Baseline × Current.
            customer_id: Identificador do cliente.
            device_id: Identificador lógico do dispositivo.
            hostname: Hostname real coletado.
            baseline_collected_at: Timestamp da baseline (opcional).
            current_collected_at: Timestamp da coleta atual (opcional).

        Returns:
            Instância de ``AuditReport`` pronta para persistência.
        """
        severity = classify_severity(report)

        return cls(
            customer_id=customer_id,
            device_id=device_id,
            hostname=hostname,
            severity=severity,
            severity_label=severity.label,
            drift_summary=report.summary(),
            drift_data=report.to_dict(),
            baseline_collected_at=baseline_collected_at,
            current_collected_at=current_collected_at,
        )
