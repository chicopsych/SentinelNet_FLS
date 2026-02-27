"""
core/services/audit_service.py
Orquestração do ciclo de auditoria de um dispositivo.

Consolida DiffEngine + classify_severity + IncidentEngine
em uma única função reutilizável pelo CLI e pela API.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from core import DiffEngine, classify_severity
from core.audit_report import Severity
from core.incident_engine import incident_engine
from core.schemas import DeviceConfig
from internalloggin.logger import setup_logger

logger = setup_logger(__name__)

_BASELINES_DIR: Path = (
    Path(__file__).resolve().parent.parent.parent
    / "inventory"
    / "baselines"
)


@dataclass(slots=True)
class AuditResult:
    """Resultado de uma auditoria individual."""

    customer_id: str
    device_id: str
    has_drift: bool
    severity: Severity | None
    incident_id: int | None
    summary: str


# ── Baseline I/O ─────────────────────────────────────────────


def load_baseline(
    customer_id: str, device_id: str
) -> DeviceConfig | None:
    """
    Carrega e valida a baseline JSON do dispositivo.
    Retorna None se o arquivo não existir ou for inválido.
    """
    path = (
        _BASELINES_DIR / customer_id / f"{device_id}.json"
    )
    if not path.exists():
        logger.warning(
            "Baseline não encontrada para %s/%s em '%s'.",
            customer_id,
            device_id,
            path,
        )
        return None
    try:
        return DeviceConfig.model_validate_json(
            path.read_text(encoding="utf-8")
        )
    except Exception as exc:  # noqa: BLE001
        logger.error(
            "Falha ao carregar baseline de %s/%s: %s",
            customer_id,
            device_id,
            exc,
        )
        return None


def save_baseline(
    customer_id: str,
    device_id: str,
    config: DeviceConfig,
) -> None:
    """Persiste configuração como nova baseline JSON."""
    path = (
        _BASELINES_DIR / customer_id / f"{device_id}.json"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        config.model_dump_json(indent=2), encoding="utf-8"
    )
    logger.info("Nova baseline salva em '%s'.", path)


def capture_initial_baseline(
    *,
    customer_id: str,
    device_id: str,
    vendor: str,
    host: str,
    port: int,
    username: str,
    password: str,
) -> tuple[bool, str]:
    """
    Tenta conectar ao dispositivo e salvar baseline inicial.

    Não sobrescreve baseline existente.
    Falhas de conexão não levantam exceção — retornam (False, msg).
    Retorna (sucesso: bool, mensagem: str).
    """
    if load_baseline(customer_id, device_id) is not None:
        return True, "Baseline já existente — mantida sem alteração."

    # Import local para evitar importação circular com drivers/
    from drivers.mikrotik_driver import MikroTikDriver  # noqa: PLC0415

    _DRIVER_MAP: dict[str, Any] = {
        "mikrotik": MikroTikDriver,
    }

    driver_cls = _DRIVER_MAP.get(vendor.lower())
    if driver_cls is None:
        logger.warning(
            "[%s/%s] Vendor '%s' sem driver — baseline pendente.",
            customer_id,
            device_id,
            vendor,
        )
        return (
            False,
            f"Vendor '{vendor}' sem driver implementado — "
            "baseline será criada na primeira auditoria.",
        )

    try:
        driver = driver_cls(
            host=host,
            port=port,
            username=username,
            password=password,
        )
        with driver:
            live_config = driver.get_config_snapshot()
        save_baseline(customer_id, device_id, live_config)
        logger.info(
            "[%s/%s] Baseline inicial capturada durante onboarding.",
            customer_id,
            device_id,
        )
        return True, "Baseline inicial capturada com sucesso."
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "[%s/%s] Falha ao capturar baseline no onboarding: %s",
            customer_id,
            device_id,
            exc,
        )
        return False, f"Baseline pendente: {exc}"


# ── Auditoria ────────────────────────────────────────────────


def audit_device(
    *,
    customer_id: str,
    device_id: str,
    vendor: str,
    live_config: DeviceConfig,
) -> AuditResult:
    """
    Compara live_config com baseline e persiste incidentes.

    Se não houver baseline, salva a configuração atual como
    referência inicial e retorna sem drift.
    """
    baseline = load_baseline(customer_id, device_id)

    if baseline is None:
        logger.warning(
            "[%s/%s] Sem baseline — snapshot salvo "
            "como referência inicial.",
            customer_id,
            device_id,
        )
        save_baseline(customer_id, device_id, live_config)
        return AuditResult(
            customer_id=customer_id,
            device_id=device_id,
            has_drift=False,
            severity=None,
            incident_id=None,
            summary="Baseline inicial criada.",
        )

    report = DiffEngine.compare(baseline, live_config)

    if not report.has_drift:
        logger.info(
            "[%s/%s] Em conformidade — nenhum desvio.",
            customer_id,
            device_id,
        )
        return AuditResult(
            customer_id=customer_id,
            device_id=device_id,
            has_drift=False,
            severity=None,
            incident_id=None,
            summary="Nenhum desvio detectado.",
        )

    severity = classify_severity(report)

    logger.warning(
        "[%s/%s] Drift detectado — %s",
        customer_id,
        device_id,
        report.summary(),
    )

    diff_dict = report.to_dict()
    incident_id = incident_engine.push_incident(
        customer_id=customer_id,
        device_id=device_id,
        severity=severity.name,
        category="configuration_drift",
        description=(
            f"Drift detectado em "
            f"{baseline.hostname}: {report.summary()}"
        ),
        payload={
            "diff": diff_dict,
            "vendor": vendor,
            "hostname": live_config.hostname,
            "os_version": live_config.os_version,
            "model": live_config.model,
        },
    )

    if incident_id:
        logger.error(
            "Incidente #%d registrado [%s] para %s/%s.",
            incident_id,
            severity.name,
            customer_id,
            device_id,
        )

    return AuditResult(
        customer_id=customer_id,
        device_id=device_id,
        has_drift=True,
        severity=severity,
        incident_id=incident_id,
        summary=report.summary(),
    )
