"""
main.py
────────
Ponto de entrada unificado do SentinelNet_FLS.

Modos de operação (via CLI):
    python main.py audit              — executa o loop de auditoria completo
    python main.py server             — inicia o Dashboard / API Flask
    python main.py topology           — executa varredura de topologia L2/L3
    python main.py topology --customer X  — scan filtrado por customer

Variáveis de ambiente relevantes para o servidor:
    FLASK_ENV   (development | production)
    FLASK_HOST  (padrão 127.0.0.1)
    FLASK_PORT  (padrão 5000)
"""

from __future__ import annotations

import argparse
import os
import sys
from typing import Any, cast

from internalloggin.logger import setup_logger

logger = setup_logger(__name__)


# ═══════════════════════════════════════════════════════
#  AUDIT — loop de auditoria por dispositivo
# ═══════════════════════════════════════════════════════

def _audit_device(vault: Any, device_info: dict[str, Any]) -> None:
    """
    Executa o ciclo completo de auditoria para um
    único dispositivo.
    """
    from core.schemas import DeviceConfig
    from core.services.audit_service import audit_device
    from drivers.mikrotik_driver import MikroTikDriver

    customer_id: str = device_info["customer_id"]
    device_id: str = device_info["device_id"]
    vendor: str = device_info.get("vendor", "").lower()

    logger.info(
        "── Auditando %s / %s ──",
        customer_id,
        device_id,
    )

    # a) Credenciais via VaultManager
    creds = vault.get_credentials(customer_id, device_id)

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
            "Incidente #%d registrado [%s] para %s/%s.",
            result.incident_id,
            result.severity.name if result.severity else "?",
            customer_id,
            device_id,
        )


def run_audit_loop() -> None:
    """
    Itera sobre todos os dispositivos do inventário.
    Cada dispositivo é auditado de forma isolada — a falha em um
    não interrompe os demais.
    """
    from core.repositories.devices_repository import (
        list_active_inventory_devices,
    )
    from utils.vault import (
        CredentialNotFoundError,
        MasterKeyNotFoundError,
        VaultError,
        VaultManager,
    )

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
            "Execute: export SENTINEL_MASTER_KEY=<chave>. Detalhe: %s",
            exc,
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
        success_count,
        failure_count,
    )


# ═══════════════════════════════════════════════════════
#  SERVER — Dashboard / API Flask
# ═══════════════════════════════════════════════════════

def run_server() -> None:
    """Inicia o servidor Flask (Dashboard + API REST)."""
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ModuleNotFoundError:
        pass  # em produção o .env não existe; variáveis já estão no ambiente

    from api import create_app
    from api.config import DevelopmentConfig, ProductionConfig

    _ENV_MAP = {
        "production": ProductionConfig,
        "prod":       ProductionConfig,
    }

    env = os.getenv("FLASK_ENV", "development").lower()
    config_class = _ENV_MAP.get(env, DevelopmentConfig)

    app = create_app(config_class=config_class)

    debug_mode = bool(app.config.get("DEBUG", False))
    if env in _ENV_MAP:
        debug_mode = False

    host = os.getenv("FLASK_HOST", "127.0.0.1")
    port = int(os.getenv("FLASK_PORT", 5000))

    logger.info(
        "Iniciando servidor Flask em %s:%d (env=%s, debug=%s)",
        host, port, env, debug_mode,
    )

    app.run(host=host, port=port, debug=debug_mode)


# ═══════════════════════════════════════════════════════
#  CLI — argparse
# ═══════════════════════════════════════════════════════

def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="sentinelnet",
        description="SentinelNet_FLS — Auditoria de rede e Dashboard.",
    )
    sub = parser.add_subparsers(dest="command")

    sub.add_parser(
        "audit",
        help="Executa o loop de auditoria completo.",
    )
    sub.add_parser(
        "server",
        help="Inicia o Dashboard / API Flask.",
    )

    topo_parser = sub.add_parser(
        "topology",
        help="Executa varredura de topologia L2/L3.",
    )
    topo_parser.add_argument(
        "--customer",
        default=None,
        help="Filtra scan por customer_id (opcional).",
    )

    return parser


def run_topology_cli(customer: str | None = None) -> None:
    """Executa scan de topologia via CLI."""
    from core.db import ensure_topology_tables
    from core.services.topology_service import run_topology_scan

    ensure_topology_tables()
    logger.info("SentinelNet_FLS — Topology Scan (CLI)")
    summary = run_topology_scan(customer_filter=customer)
    logger.info(
        "Resumo: %d dispositivo(s), %d nó(s), %d drift(s).",
        summary["devices_scanned"],
        summary["nodes_discovered"],
        summary["drifts"],
    )


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    if args.command == "audit":
        run_audit_loop()
    elif args.command == "server":
        run_server()
    elif args.command == "topology":
        run_topology_cli(customer=args.customer)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
