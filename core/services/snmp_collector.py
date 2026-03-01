"""
core/services/snmp_collector.py
───────────────────────────────
Coleta de tabelas de topologia via SNMP (fallback/complemento ao CLI).

Design:
    - Import dinâmico de pysnmp (mesmo padrão do reachability_service)
    - SNMPv2c síncrono via pysnmp.hlapi
    - Retorna os mesmos schemas Pydantic (ARPEntry, MACEntry, LLDPNeighbor)
    - Usado como fallback quando CLI falha ou para devices sem SSH
"""

from __future__ import annotations

import importlib
import re
from typing import Any

from core.constants import (
    SNMP_OID_ARP_TABLE,
    SNMP_OID_LLDP_REM,
    SNMP_OID_MAC_TABLE_D1D,
)
from core.schemas import ARPEntry, LLDPNeighbor, MACEntry
from internalloggin.logger import setup_logger

logger = setup_logger(__name__)


def _load_pysnmp() -> Any | None:
    """Carrega pysnmp.hlapi dinamicamente. Retorna None se não instalado."""
    try:
        return importlib.import_module("pysnmp.hlapi")
    except ImportError:
        logger.warning("pysnmp não instalado — coleta SNMP indisponível.")
        return None


def snmp_walk(
    host: str,
    community: str,
    oid: str,
    *,
    port: int = 161,
    timeout: int = 2,
    max_rows: int = 5000,
) -> list[tuple[str, str]]:
    """
    Executa SNMP GETNEXT walk a partir de um OID base.

    Retorna lista de (oid_string, valor_string). Retorna [] se pysnmp
    não estiver disponível ou ocorrer erro.
    """
    hlapi = _load_pysnmp()
    if hlapi is None:
        return []

    results: list[tuple[str, str]] = []
    try:
        iterator = hlapi.nextCmd(
            hlapi.SnmpEngine(),
            hlapi.CommunityData(community, mpModel=1),
            hlapi.UdpTransportTarget((host, port), timeout=timeout, retries=1),
            hlapi.ContextData(),
            hlapi.ObjectType(hlapi.ObjectIdentity(oid)),
            lexicographicMode=False,
        )

        count = 0
        for err_indication, err_status, _, var_binds in iterator:
            if err_indication or err_status:
                logger.debug(
                    "SNMP walk %s em %s: err=%s status=%s",
                    oid, host, err_indication, err_status,
                )
                break
            for oid_val, val in var_binds:
                results.append((str(oid_val), str(val)))
            count += 1
            if count >= max_rows:
                break

    except Exception as exc:
        logger.warning("Falha no SNMP walk %s em %s: %s", oid, host, exc)

    logger.debug("SNMP walk %s em %s: %d resultados.", oid, host, len(results))
    return results


# ═══════════════════════════════════════════════════════════════════════════════
# Funções de alto nível — retornam schemas Pydantic
# ═══════════════════════════════════════════════════════════════════════════════


def _mac_from_hex(hex_str: str) -> str | None:
    """Converte hex-string SNMP (ex: '0x001A2B3C4D5E' ou '00:1A:2B:3C:4D:5E') para MAC."""
    cleaned = re.sub(r"[^0-9a-fA-F]", "", hex_str)
    if len(cleaned) == 12:
        return ":".join(cleaned[i : i + 2].upper() for i in range(0, 12, 2))
    return None


def collect_arp_via_snmp(
    host: str,
    community: str,
    timeout: int = 2,
) -> list[ARPEntry]:
    """
    Coleta tabela ARP via SNMP (ipNetToMediaTable).

    OID structure: ipNetToMediaPhysAddress.ifIndex.ip1.ip2.ip3.ip4 = MAC
    """
    raw = snmp_walk(host, community, SNMP_OID_ARP_TABLE, timeout=timeout)
    entries: list[ARPEntry] = []

    for oid_str, val in raw:
        # ipNetToMediaPhysAddress: .1.3.6.1.2.1.4.22.1.2.<ifIndex>.<ip>
        if ".4.22.1.2." not in oid_str:
            continue
        parts = oid_str.split(".")
        if len(parts) < 4:
            continue
        ip_address = ".".join(parts[-4:])
        mac = _mac_from_hex(val)
        if mac and ip_address:
            try:
                entries.append(ARPEntry(ip_address=ip_address, mac_address=mac))
            except Exception:
                pass

    logger.info("SNMP ARP de %s: %d entradas.", host, len(entries))
    return entries


def collect_mac_via_snmp(
    host: str,
    community: str,
    timeout: int = 2,
) -> list[MACEntry]:
    """
    Coleta tabela MAC via SNMP (dot1dTpFdbTable).

    OID: dot1dTpFdbAddress (.1.3.6.1.2.1.17.4.3.1.1) = MAC
    """
    raw = snmp_walk(host, community, SNMP_OID_MAC_TABLE_D1D, timeout=timeout)
    entries: list[MACEntry] = []

    for oid_str, val in raw:
        if ".17.4.3.1.1." not in oid_str:
            continue
        mac = _mac_from_hex(val)
        if mac:
            try:
                entries.append(MACEntry(mac_address=mac))
            except Exception:
                pass

    logger.info("SNMP MAC de %s: %d entradas.", host, len(entries))
    return entries


def collect_lldp_via_snmp(
    host: str,
    community: str,
    timeout: int = 2,
) -> list[LLDPNeighbor]:
    """
    Coleta vizinhos LLDP via SNMP (lldpRemTable).

    OID base: 1.0.8802.1.1.2.1.4
    """
    raw = snmp_walk(host, community, SNMP_OID_LLDP_REM, timeout=timeout)
    # LLDP MIB é complexa; parsing simplificado por sub-OID
    neighbors: list[LLDPNeighbor] = []

    # Agrupar por índice remoto
    remote_data: dict[str, dict[str, str]] = {}
    for oid_str, val in raw:
        parts = oid_str.split(".")
        if len(parts) < 3:
            continue
        # Último componente numérico é o index_key
        index_key = ".".join(parts[-3:])

        if ".1.4.1.9." in oid_str:   # lldpRemSysName
            remote_data.setdefault(index_key, {})["remote_device"] = val
        elif ".1.4.1.7." in oid_str:  # lldpRemPortId
            remote_data.setdefault(index_key, {})["remote_port"] = val
        elif ".1.4.1.10." in oid_str:  # lldpRemSysDesc
            remote_data.setdefault(index_key, {})["remote_description"] = val

    for data in remote_data.values():
        try:
            neighbors.append(LLDPNeighbor(**data))
        except Exception:
            pass

    logger.info("SNMP LLDP de %s: %d vizinhos.", host, len(neighbors))
    return neighbors
