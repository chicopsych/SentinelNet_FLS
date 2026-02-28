"""
main.py
────────
Ponto de entrada do SentinelNet_FLS — Loop de Auditoria Completo.

Fluxo:
    1. Carrega inventário persistido (SQLite) da tabela inventory_devices.
    2. Para cada dispositivo:
       a) Obtém credenciais via VaultManager (sem expor segredos nos logs).
       b) Instancia o driver correto (ex: MikroTikDriver).
       c) Coleta snapshot de configuração atual.
       d) Carrega a Baseline JSON de
          inventory/baselines/<cust>/<dev>.json.
       e) Compara snapshot × baseline com DiffEngine.
       f) Persiste desvios no SQLite via IncidentEngine.
    3. Falha isolada por dispositivo — demais continuam sendo auditados.
"""

from __future__ import annotations

from typing import Any, cast

from core.repositories.devices_repository import (
    list_active_inventory_devices,
)
from core.services.audit_service import audit_device
from drivers.mikrotik_driver import MikroTikDriver
from internalloggin.logger import setup_logger
from utils.vault import (
    CredentialNotFoundError,
    MasterKeyNotFoundError,
    VaultError,
    VaultManager,
)

logger = setup_logger(__name__)

from core.schemas import DeviceConfig  # ajuste o caminho real


# ── Ciclo de auditoria por dispositivo ───────────────


def _audit_device(
    vault: VaultManager, device_info: dict[str, Any]
) -> None:
    """
    Executa o ciclo completo de auditoria para um
    único dispositivo.

    Raises:
        VaultError: Credenciais ausentes ou cofre.
        ConnectionError / TimeoutError: SSH.
        Exception: Qualquer outro erro inesperado.
    """
    customer_id: str = device_info["customer_id"]
    device_id: str = device_info["device_id"]
    vendor: str = device_info.get(
        "vendor", ""
    ).lower()

    logger.info(
        "── Auditando %s / %s ──",
        customer_id,
        device_id,
    )

    # a) Credenciais via VaultManager
    creds = vault.get_credentials(
        customer_id, device_id
    )

    # b) Instancia o driver correto
    if vendor == "mikrotik":
        driver = MikroTikDriver(
            host=creds["host"],
            username=creds["username"],
            password=creds["password"],
            port=int(creds.get("port", 22)),
        )
    else:
        msg = (
            f"Vendor '{vendor}' ainda não tem "
            "driver implementado."
        )
        raise ValueError(msg)

    # c) Coleta snapshot atual via SSH
    current = cast(DeviceConfig, None)
    with driver:
        current = driver.get_config_snapshot()

    logger.info(
        "Snapshot coletado: %s  OS=%s  modelo=%s",
        current.hostname,
        current.os_version,
        current.model,
    )

    # d-f) Compara com baseline e persiste incidente
    result = audit_device(
        customer_id=customer_id,
        device_id=device_id,
        vendor=vendor,
        live_config=current,
    )

    if result.has_drift and result.incident_id:
        logger.error(
            "Incidente #%d registrado [%s] para "
            "%s/%s.",
            result.incident_id,
            result.severity.name
            if result.severity
            else "?",
            customer_id,
            device_id,
        )


# ── Loop principal ────────────────────────────────────────────────────────


def run_audit_loop() -> None:
    """
    Itera sobre todos os dispositivos do inventário.
    Cada dispositivo é auditado de forma isolada — a falha em um
    não interrompe os demais.
    """
    logger.info("SentinelNet_FLS — Loop de Auditoria iniciado.")
    inventory_devices = list_active_inventory_devices()
    logger.info(
        "Dispositivos ativos no inventário: %d", len(inventory_devices)
    )

    if not inventory_devices:
        logger.warning(
            "Nenhum dispositivo ativo encontrado no inventário persistido. "
            "Auditoria encerrada."
        )
        return

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

    for device_info in inventory_devices:
        customer_id = device_info.get("customer_id", "?")
        device_id = device_info.get("device_id", "?")
        try:
            _audit_device(vault, device_info)
            success_count += 1
        except CredentialNotFoundError as exc:
            logger.error(
                "[%s/%s] Credenciais não encontradas no cofre: %s",
                customer_id, device_id, exc,
            )
            failure_count += 1
        except VaultError as exc:
            logger.error(
                "[%s/%s] Erro no cofre de credenciais: %s",
                customer_id, device_id, exc,
            )
            failure_count += 1
        except (ConnectionError, TimeoutError, OSError) as exc:
            logger.error(
                "[%s/%s] Falha de conectividade com o dispositivo: %s",
                customer_id, device_id, exc,
            )
            failure_count += 1
        except Exception as exc:  # noqa: BLE001
            logger.exception(
                "[%s/%s] Erro inesperado durante auditoria: %s",
                customer_id, device_id, exc,
            )
            failure_count += 1

    logger.info(
        "Auditoria concluída — sucesso: %d  falha: %d.",
        success_count, failure_count,
    )


def main() -> None:
    run_audit_loop()


if __name__ == "__main__":
    main()
