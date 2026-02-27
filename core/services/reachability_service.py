"""
core/services/reachability_service.py
Testes de conectividade: ICMP (ping) e SNMP.

Agnóstico à interface — usado pelo CLI e pela API web.
"""

from __future__ import annotations

import importlib
import subprocess
from typing import Any

from utils.vault import (
    MasterKeyNotFoundError,
    VaultError,
    VaultManager,
)

_SNMP_SYS_DESCR_OID = "1.3.6.1.2.1.1.1.0"


def load_snmp_communities() -> (
    dict[tuple[str, str], str]
):
    """
    Carrega snmp_community do cofre, sem expor segredos.

    Retorna dict {(customer_id, device_id): community}.
    """
    try:
        vault = VaultManager()
        payload = vault.load_payload()
    except (MasterKeyNotFoundError, VaultError):
        return {}

    communities: dict[tuple[str, str], str] = {}
    for customer_id, devices in payload.items():
        if not isinstance(devices, dict):
            continue
        for device_id, data in devices.items():
            if not isinstance(data, dict):
                continue
            community = data.get("snmp_community")
            if community:
                communities[
                    (customer_id, device_id)
                ] = str(community)
    return communities


def ping_host(
    host: str, timeout: int = 1
) -> bool:
    """Retorna True se houver resposta ICMP."""
    if not host:
        return False
    try:
        result = subprocess.run(
            [
                "ping",
                "-c",
                "1",
                "-W",
                str(timeout),
                host,
            ],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=timeout + 1,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return result.returncode == 0


def snmp_get_sysdescr(
    host: str,
    community: str,
    timeout: int = 1,
    port: int = 161,
) -> bool | None:
    """SNMP GET sysDescr.0. True se houver resposta."""
    if not host or not community:
        return False
    try:
        hlapi = importlib.import_module("pysnmp.hlapi")
        CommunityData = hlapi.CommunityData
        ContextData = hlapi.ContextData
        ObjectIdentity = hlapi.ObjectIdentity
        ObjectType = hlapi.ObjectType
        SnmpEngine = hlapi.SnmpEngine
        UdpTransportTarget = hlapi.UdpTransportTarget
        getCmd = hlapi.getCmd
    except ImportError:
        return None

    try:
        iterator = getCmd(
            SnmpEngine(),
            CommunityData(community, mpModel=1),
            UdpTransportTarget(
                (host, port),
                timeout=timeout,
                retries=0,
            ),
            ContextData(),
            ObjectType(
                ObjectIdentity(_SNMP_SYS_DESCR_OID)
            ),
        )
        err_ind, err_st, _, _ = next(iterator)
        if err_ind or err_st:
            return False
    except Exception:
        return False

    return True


def check_device_reachability(
    *,
    host: str,
    snmp_community: str | None,
    timeout: int = 1,
) -> dict[str, Any]:
    """Retorna status de ping e SNMP para um ativo."""
    ping_ok = ping_host(host, timeout=timeout)
    snmp_ok: bool | None = None
    if snmp_community:
        snmp_ok = snmp_get_sysdescr(
            host, snmp_community, timeout=timeout
        )

    is_warning = (not ping_ok) or (snmp_ok is False)
    return {
        "ping_ok": ping_ok,
        "snmp_ok": snmp_ok,
        "warning": is_warning,
    }
