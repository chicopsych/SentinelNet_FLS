"""
main.py
────────
Ponto de entrada do SentinelNet_FLS — Loop de Auditoria Completo.

Fluxo:
    1. Carrega inventário de inventory/customer/customer.py.
    2. Para cada dispositivo:
       a) Obtém credenciais via VaultManager (sem expor segredos nos logs).
       b) Instancia o driver correto (ex: MikroTikDriver).
       c) Coleta snapshot de configuração atual.
       d) Carrega a Baseline JSON de inventory/baselines/<customer>/<device>.json.
       e) Compara snapshot × baseline com DiffEngine.
       f) Persiste desvios no SQLite via IncidentEngine.
    3. Falha isolada por dispositivo — demais continuam sendo auditados.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from core import DiffEngine
from core.incident_engine import incident_engine
from core.schemas import DeviceConfig
from drivers.mikrotik_driver import MikroTikDriver
from internalloggin.logger import setup_logger
from inventory.customer.customer import DEVICE_INVENTORY
from utils.vault import CredentialNotFoundError, MasterKeyNotFoundError, VaultError, VaultManager

logger = setup_logger(__name__)

# Diretório das baselines JSON — inventory/baselines/<customer_id>/<device_id>.json
_BASELINES_DIR = Path(__file__).resolve().parent / "inventory" / "baselines"


# ── Baseline ───────────────────────────────────────────────────────────────────


def _load_baseline(customer_id: str, device_id: str) -> DeviceConfig | None:
    """
    Carrega e valida a baseline JSON do dispositivo indicado.
    Retorna None se o arquivo não existir ou estiver malformado.
    """
    path = _BASELINES_DIR / customer_id / f"{device_id}.json"
    if not path.exists():
        logger.warning(
            "Baseline não encontrada para %s/%s em '%s'.",
            customer_id, device_id, path,
        )
        return None
    try:
        return DeviceConfig.model_validate_json(path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        logger.error(
            "Falha ao carregar baseline de %s/%s: %s",
            customer_id, device_id, exc,
        )
        return None


def _save_baseline(customer_id: str, device_id: str, config: DeviceConfig) -> None:
    """Persiste a configuração atual como nova baseline JSON (primeiro acesso)."""
    path = _BASELINES_DIR / customer_id / f"{device_id}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(config.model_dump_json(indent=2), encoding="utf-8")
    logger.info("Nova baseline salva em '%s'.", path)


# ── Ciclo de auditoria por dispositivo ────────────────────────────────────────


def _classify_severity(diff_dict: dict[str, Any]) -> str:
    """
    Determina a severidade máxima do drift detectado.

    Hierarquia (pior caso):
        CRITICAL > HIGH > MEDIUM > LOW
    """
    fw = diff_dict.get("firewall_audit", {})
    if fw.get("position_drift"):
        return "CRITICAL"
    if fw.get("missing_rules") or fw.get("extra_rules"):
        return "HIGH"
    if (
        diff_dict.get("added")
        or diff_dict.get("removed")
        or diff_dict.get("modified")
        or fw.get("parameter_drift")
    ):
        return "MEDIUM"
    return "LOW"


def _audit_device(vault: VaultManager, device_info: dict[str, Any]) -> None:
    """
    Executa o ciclo completo de auditoria para um único dispositivo.

    Raises:
        VaultError: Credenciais ausentes ou cofre inacessível.
        ConnectionError / TimeoutError: Falha de acesso SSH ao dispositivo.
        Exception: Qualquer outro erro inesperado.
    """
    customer_id: str = device_info["customer_id"]
    device_id: str = device_info["device_id"]
    vendor: str = device_info.get("vendor", "").lower()

    logger.info("── Auditando %s / %s ──", customer_id, device_id)

    # a) Credenciais via VaultManager (sem logar valores sensíveis)
    creds = vault.get_credentials(customer_id, device_id)

    # b) Instancia o driver correto com base no vendor
    if vendor == "mikrotik":
        driver = MikroTikDriver(
            host=creds["host"],
            username=creds["username"],
            password=creds["password"],
            port=int(creds.get("port", 22)),
        )
    else:
        raise ValueError(f"Vendor '{vendor}' ainda não tem driver implementado.")

    # c) Coleta snapshot atual via SSH (context manager garante disconnect)
    with driver:
        current: DeviceConfig = driver.get_config_snapshot()

    logger.info(
        "Snapshot coletado: %s  OS=%s  modelo=%s",
        current.hostname, current.os_version, current.model,
    )

    # d) Carrega baseline JSON
    baseline = _load_baseline(customer_id, device_id)
    if baseline is None:
        logger.warning(
            "[%s/%s] Sem baseline prévia — snapshot salvo como referência inicial.",
            customer_id, device_id,
        )
        _save_baseline(customer_id, device_id, current)
        return

    # e) Compara snapshot × baseline
    report = DiffEngine.compare(baseline, current)

    if not report.has_drift:
        logger.info("[%s/%s] Em conformidade — nenhum desvio detectado.", customer_id, device_id)
        return

    logger.warning("[%s/%s] Drift detectado — %s", customer_id, device_id, report.summary())

    # f) Persiste o incidente no SQLite via IncidentEngine
    diff_dict = report.to_dict()
    severity = _classify_severity(diff_dict)

    incident_id = incident_engine.push_incident(
        customer_id=customer_id,
        device_id=device_id,
        severity=severity,
        category="configuration_drift",
        description=f"Drift detectado em {current.hostname}: {report.summary()}",
        payload={
            "diff": diff_dict,
            "vendor": vendor,
            "hostname": current.hostname,
            "os_version": current.os_version,
            "model": current.model,
        },
    )

    if incident_id:
        logger.error(
            "Incidente #%d registrado [%s] para %s/%s.",
            incident_id, severity, customer_id, device_id,
        )


# ── Loop principal ─────────────────────────────────────────────────────────────


def run_audit_loop() -> None:
    """
    Itera sobre todos os dispositivos do inventário.
    Cada dispositivo é auditado de forma isolada — a falha em um
    não interrompe os demais.
    """
    logger.info("SentinelNet_FLS — Loop de Auditoria iniciado.")
    logger.info("Dispositivos no inventário: %d", len(DEVICE_INVENTORY))

    # Inicializa o VaultManager uma única vez para toda a rodada
    try:
        vault = VaultManager()
    except MasterKeyNotFoundError as exc:
        logger.critical(
            "SENTINEL_MASTER_KEY não configurada. "
            "Execute: export SENTINEL_MASTER_KEY=<chave>. Detalhe: %s", exc,
        )
        return
    except VaultError as exc:
        logger.critical("VaultManager falhou ao inicializar: %s", exc)
        return

    success_count = 0
    failure_count = 0

    for device_info in DEVICE_INVENTORY:
        customer_id = device_info.get("customer_id", "?")
        device_id = device_info.get("device_id", "?")
        try:
            _audit_device(vault, device_info)
            success_count += 1
        except CredentialNotFoundError as exc:
            logger.error("[%s/%s] Credenciais não encontradas no cofre: %s", customer_id, device_id, exc)
            failure_count += 1
        except VaultError as exc:
            logger.error("[%s/%s] Erro no cofre de credenciais: %s", customer_id, device_id, exc)
            failure_count += 1
        except (ConnectionError, TimeoutError, OSError) as exc:
            logger.error("[%s/%s] Falha de conectividade com o dispositivo: %s", customer_id, device_id, exc)
            failure_count += 1
        except Exception as exc:  # noqa: BLE001
            logger.exception("[%s/%s] Erro inesperado durante auditoria: %s", customer_id, device_id, exc)
            failure_count += 1

    logger.info(
        "Auditoria concluída — sucesso: %d  falha: %d.",
        success_count, failure_count,
    )


def main() -> None:
    run_audit_loop()


if __name__ == "__main__":
    main()
