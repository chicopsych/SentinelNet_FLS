"""
core/diff_engine.py
───────────────────
Motor de comparação semântica para detecção de Configuration Drift.

Compara dois objetos DeviceConfig (Baseline × Current) e produz um relatório
estruturado de discrepâncias, classificadas em:

    - **added**    : Configurações presentes no estado atual mas ausentes na baseline.
    - **removed**  : Configurações presentes na baseline mas ausentes no estado atual.
    - **modified** : Configurações presentes em ambos, porém com valores divergentes.

Design Decisions
────────────────
1. Comparação Ordinal para listas (interfaces, routes, firewall_rules):
   Itens são pareados por índice (posição). Se o current for mais longo,
   itens excedentes são reportados como "added"; se o baseline for mais
   longo, itens faltantes são reportados como "removed". Regras no mesmo
   índice são comparadas campo-a-campo.

2. Exclusão de campos voláteis:
   O parâmetro ``exclude_fields`` (default: ``{"collected_at"}``) permite ao
   chamador ignorar campos que mudam a cada coleta e gerariam ruído
   (falsos positivos) no relatório de auditoria.

3. Sem dependências externas:
   A comparação é implementada manualmente sobre ``model_dump()`` dos
   modelos Pydantic, sem libs como ``deepdiff``. Isso garante controle
   total sobre o formato do relatório e evita dependências adicionais.

4. Logging contextualizado:
   Cada drift detectado é logado com nível WARNING para rastreabilidade
   operacional. O logger segue o padrão do projeto (``setup_logger``).
"""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel

from core.schemas import DeviceConfig
from internalloggin.logger import setup_logger

logger = setup_logger("DiffEngine")

# Campos que são listas de sub-modelos Pydantic no DeviceConfig
_LIST_FIELDS = ("interfaces", "routes", "firewall_rules")

# Campos excluídos por padrão da comparação (voláteis / não-semânticos)
_DEFAULT_EXCLUDE: set[str] = {"collected_at"}


class DiffReport:
    """
    Encapsula o resultado de uma comparação Baseline × Current.

    Atributos:
        added    (dict[str, Any]): Configurações adicionadas no estado atual.
        removed  (dict[str, Any]): Configurações removidas em relação à baseline.
        modified (dict[str, Any]): Configurações com valores divergentes.
    """

    __slots__ = ("added", "removed", "modified")

    def __init__(self) -> None:
        self.added: dict[str, Any] = {}
        self.removed: dict[str, Any] = {}
        self.modified: dict[str, Any] = {}

    # ── Helpers ───────────────────────────────────────────────────────────────

    @property
    def has_drift(self) -> bool:
        """Retorna True se qualquer discrepância foi detectada."""
        return bool(self.added or self.removed or self.modified)

    def to_dict(self) -> dict[str, Any]:
        """Serializa o relatório para um dicionário simples."""
        return {
            "added": self.added,
            "removed": self.removed,
            "modified": self.modified,
        }

    def summary(self) -> str:
        """Resumo legível em uma linha para logs."""
        counts = (
            f"added={len(self.added)}",
            f"removed={len(self.removed)}",
            f"modified={len(self.modified)}",
        )
        return f"DiffReport({', '.join(counts)})"

    def __repr__(self) -> str:  # pragma: no cover
        return self.summary()


class DiffEngine:
    """
    Motor de comparação para detectar Configuration Drift.

    Uso típico::

        report = DiffEngine.compare(baseline_cfg, current_cfg)
        if report.has_drift:
            print(report.to_dict())
    """

    # ── API Pública ───────────────────────────────────────────────────────────

    @staticmethod
    def compare(
        baseline: DeviceConfig,
        current: DeviceConfig,
        exclude_fields: Optional[set[str]] = None,
    ) -> DiffReport:
        """
        Compara dois snapshots de configuração e retorna um relatório de drift.

        Args:
            baseline:       Estado esperado (fonte de verdade).
            current:        Estado real coletado do equipamento.
            exclude_fields: Conjunto de nomes de campo a ignorar na comparação.
                            Default: ``{"collected_at"}``.

        Returns:
            DiffReport com as discrepâncias classificadas.
        """
        if exclude_fields is None:
            exclude_fields = _DEFAULT_EXCLUDE.copy()

        report = DiffReport()

        logger.info(
            "Iniciando comparação: baseline='%s' vs current='%s'",
            baseline.hostname,
            current.hostname,
        )

        # 1. Campos escalares (hostname, vendor, model, os_version)
        DiffEngine._compare_scalar_fields(baseline, current, exclude_fields, report)

        # 2. Campos de lista (interfaces, routes, firewall_rules)
        for field_name in _LIST_FIELDS:
            if field_name in exclude_fields:
                continue
            baseline_list: list[BaseModel] = getattr(baseline, field_name)
            current_list: list[BaseModel] = getattr(current, field_name)
            DiffEngine._compare_list_ordinal(
                field_name, baseline_list, current_list, report,
            )

        if report.has_drift:
            logger.warning("Drift detectado — %s", report.summary())
        else:
            logger.info("Nenhuma discrepância detectada. Equipamento em conformidade.")

        return report

    # ── Internals ─────────────────────────────────────────────────────────────

    @staticmethod
    def _compare_scalar_fields(
        baseline: DeviceConfig,
        current: DeviceConfig,
        exclude_fields: set[str],
        report: DiffReport,
    ) -> None:
        """
        Compara os campos escalares (não-lista) do DeviceConfig.

        Um campo é considerado escalar se **não** pertence a ``_LIST_FIELDS``.
        Campos cujo nome esteja em ``exclude_fields`` são silenciosamente
        ignorados.
        """
        baseline_data = baseline.model_dump()
        current_data = current.model_dump()

        scalar_keys = {
            k for k in baseline_data
            if k not in _LIST_FIELDS and k not in exclude_fields
        }
        # Incluir chaves novas que possam existir apenas no current
        scalar_keys |= {
            k for k in current_data
            if k not in _LIST_FIELDS and k not in exclude_fields
        }

        for key in sorted(scalar_keys):
            expected = baseline_data.get(key)
            actual = current_data.get(key)

            if expected == actual:
                continue

            if key not in current_data:
                report.removed[key] = expected
                logger.warning(
                    "Drift [scalar]: campo '%s' removido (esperado: %r).", key, expected,
                )
            elif key not in baseline_data:
                report.added[key] = actual
                logger.warning(
                    "Drift [scalar]: campo '%s' adicionado (valor: %r).", key, actual,
                )
            else:
                report.modified[key] = {"expected": expected, "actual": actual}
                logger.warning(
                    "Drift [scalar]: campo '%s' alterado — esperado=%r, atual=%r.",
                    key, expected, actual,
                )

    @staticmethod
    def _compare_list_ordinal(
        field_name: str,
        baseline_list: list[BaseModel],
        current_list: list[BaseModel],
        report: DiffReport,
    ) -> None:
        """
        Compara duas listas de modelos Pydantic por posição ordinal (índice).

        Para cada par ``(baseline[i], current[i])``:
            - Se ambos existem, compara campo-a-campo via ``model_dump()``.
              Campos divergentes são adicionados à seção ``modified``.
            - Itens em ``current`` além do tamanho de ``baseline`` → ``added``.
            - Itens em ``baseline`` além do tamanho de ``current`` → ``removed``.
        """
        min_len = min(len(baseline_list), len(current_list))
        modifications: list[dict[str, Any]] = []
        additions: list[dict[str, Any]] = []
        removals: list[dict[str, Any]] = []

        # ── Comparação par-a-par nos índices comuns ───────────────────────────
        for idx in range(min_len):
            expected_data = baseline_list[idx].model_dump()
            actual_data = current_list[idx].model_dump()

            changes: dict[str, dict[str, Any]] = {}
            all_keys = set(expected_data) | set(actual_data)

            for key in sorted(all_keys):
                exp_val = expected_data.get(key)
                act_val = actual_data.get(key)
                if exp_val != act_val:
                    changes[key] = {"expected": exp_val, "actual": act_val}

            if changes:
                modifications.append({"index": idx, "changes": changes})
                logger.warning(
                    "Drift [%s][%d]: %d campo(s) alterado(s) — %s",
                    field_name, idx, len(changes), list(changes.keys()),
                )

        # ── Itens adicionados (current mais longo que baseline) ───────────────
        for idx in range(min_len, len(current_list)):
            item_data = current_list[idx].model_dump()
            additions.append({"index": idx, "item": item_data})
            logger.warning(
                "Drift [%s][%d]: item adicionado — %s",
                field_name, idx, _brief_item(item_data),
            )

        # ── Itens removidos (baseline mais longo que current) ─────────────────
        for idx in range(min_len, len(baseline_list)):
            item_data = baseline_list[idx].model_dump()
            removals.append({"index": idx, "item": item_data})
            logger.warning(
                "Drift [%s][%d]: item removido — %s",
                field_name, idx, _brief_item(item_data),
            )

        # ── Persiste no relatório apenas se houve discrepâncias ───────────────
        if modifications:
            report.modified.setdefault(field_name, []).extend(modifications)
        if additions:
            report.added.setdefault(field_name, []).extend(additions)
        if removals:
            report.removed.setdefault(field_name, []).extend(removals)


# ─── Helpers internos ─────────────────────────────────────────────────────────

def _brief_item(data: dict[str, Any], max_fields: int = 4) -> str:
    """Gera resumo curto de um item para logs (evita linhas gigantes)."""
    parts = []
    for key, value in list(data.items())[:max_fields]:
        if value is not None:
            parts.append(f"{key}={value!r}")
    suffix = ", ..." if len(data) > max_fields else ""
    return "{" + ", ".join(parts) + suffix + "}"
