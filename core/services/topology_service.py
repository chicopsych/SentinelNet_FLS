"""
core/services/topology_service.py
──────────────────────────────────
Orquestra a coleta, correlação e detecção de desvios de topologia.

Fluxo principal (``run_topology_scan``):
    1. Para cada dispositivo ativo do customer:
       a) Coleta ARP, MAC e LLDP via CLI (driver SSH).
       b) Fallback via SNMP se CLI falhar.
    2. Correlaciona L2 (MAC→porta→VLAN) com L3 (IP→MAC).
    3. Persiste nós e entradas brutas no SQLite.
    4. Detecta VLAN Drift e gera incidentes.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from core.base_driver import NetworkDeviceDriver
from core.constants import (
    INCIDENT_CATEGORY_UNAUTHORIZED_NODE,
    INCIDENT_CATEGORY_VLAN_DRIFT,
)
from core.incident_engine import incident_engine
from core.repositories.devices_repository import (
    list_active_inventory_devices,
)
from core.repositories.topology_repository import (
    count_distinct_vlans,
    count_nodes_by_customer,
    get_authorized_vlan_map,
    insert_arp_entries,
    insert_lldp_entries,
    insert_mac_entries,
    list_nodes,
    upsert_node,
)
from core.schemas import ARPEntry, LLDPNeighbor, MACEntry, NetworkNode
from core.services.reachability_service import load_snmp_communities
from core.services.snmp_collector import (
    collect_arp_via_snmp,
    collect_lldp_via_snmp,
    collect_mac_via_snmp,
)
from internalloggin.logger import setup_logger

logger = setup_logger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# OUI Lookup (fabricante pelo MAC)
# ═══════════════════════════════════════════════════════════════════════════════

_OUI_CACHE: dict[str, str] | None = None


def _load_oui_db() -> dict[str, str]:
    """
    Carrega mapeamento OUI → vendor do arquivo IEEE.

    Espera formato: 'AABBCC  vendor name' (um por linha).
    """
    global _OUI_CACHE  # noqa: PLW0603
    if _OUI_CACHE is not None:
        return _OUI_CACHE

    from pathlib import Path

    oui_path = Path(__file__).resolve().parent.parent.parent / "data" / "oui.txt"
    _OUI_CACHE = {}
    if not oui_path.exists():
        logger.debug("Arquivo OUI não encontrado em %s — lookup desabilitado.", oui_path)
        return _OUI_CACHE

    try:
        for line in oui_path.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split(None, 1)
            if len(parts) == 2 and len(parts[0]) == 6:
                _OUI_CACHE[parts[0].upper()] = parts[1]
    except Exception as exc:
        logger.warning("Erro ao carregar OUI DB: %s", exc)

    logger.debug("OUI DB carregado: %d fabricantes.", len(_OUI_CACHE))
    return _OUI_CACHE


def resolve_vendor_oui(mac_address: str) -> str:
    """Retorna o nome do fabricante pelo prefixo OUI do MAC, ou 'unknown'."""
    oui_db = _load_oui_db()
    prefix = mac_address.replace(":", "").replace("-", "")[:6].upper()
    return oui_db.get(prefix, "unknown")


# ═══════════════════════════════════════════════════════════════════════════════
# Correlação L2/L3
# ═══════════════════════════════════════════════════════════════════════════════


def correlate_l2_l3(
    arp_entries: list[ARPEntry],
    mac_entries: list[MACEntry],
) -> list[NetworkNode]:
    """
    Mescla tabela ARP (L3: IP→MAC) com tabela MAC (L2: MAC→porta→VLAN).

    O MAC address é a chave de junção. O resultado é uma lista de
    NetworkNode com visão unificada.
    """
    # Indexar MAC entries por mac_address
    mac_index: dict[str, MACEntry] = {}
    for entry in mac_entries:
        mac_index[entry.mac_address] = entry

    # Indexar ARP entries por mac_address
    arp_index: dict[str, ARPEntry] = {}
    for entry in arp_entries:
        arp_index[entry.mac_address] = entry

    # Unir todos os MACs conhecidos
    all_macs = set(arp_index.keys()) | set(mac_index.keys())
    now = datetime.now(timezone.utc)

    nodes: list[NetworkNode] = []
    for mac in all_macs:
        arp = arp_index.get(mac)
        mac_e = mac_index.get(mac)

        node = NetworkNode(
            mac_address=mac,
            ip_address=arp.ip_address if arp else None,
            vlan_id=(
                mac_e.vlan_id if mac_e and mac_e.vlan_id
                else (arp.vlan_id if arp else None)
            ),
            switch_port=mac_e.switch_port if mac_e else None,
            vendor_oui=resolve_vendor_oui(mac),
            last_seen=now,
        )
        nodes.append(node)

    logger.info(
        "Correlação L2/L3: %d ARP + %d MAC → %d nós unificados.",
        len(arp_entries), len(mac_entries), len(nodes),
    )
    return nodes


# ═══════════════════════════════════════════════════════════════════════════════
# Detecção de VLAN Drift
# ═══════════════════════════════════════════════════════════════════════════════


def detect_vlan_drift(
    customer_id: str,
    current_nodes: list[NetworkNode],
) -> list[dict[str, Any]]:
    """
    Compara nós atuais com o mapa de VLANs autorizadas.

    Gera incidentes para:
    - MAC autorizado encontrado em VLAN diferente da autorizada → VLAN Drift (HIGH)
    - MAC não autorizado em qualquer VLAN → Nó não-autorizado (MEDIUM)

    Returns:
        Lista de dicts descrevendo cada drift detectado.
    """
    authorized_map = get_authorized_vlan_map(customer_id)
    drifts: list[dict[str, Any]] = []

    for node in current_nodes:
        if node.vlan_id is None:
            continue

        mac = node.mac_address

        if mac in authorized_map:
            allowed_vlans = authorized_map[mac]
            if node.vlan_id not in allowed_vlans:
                drift = {
                    "type": "vlan_drift",
                    "mac_address": mac,
                    "ip_address": node.ip_address,
                    "expected_vlans": sorted(allowed_vlans),
                    "found_vlan": node.vlan_id,
                    "switch_port": node.switch_port,
                    "severity": "HIGH",
                    "description": (
                        f"MAC {mac} detectado na VLAN {node.vlan_id} — "
                        f"autorizado apenas nas VLANs {sorted(allowed_vlans)}."
                    ),
                }
                drifts.append(drift)
                logger.warning(
                    "VLAN DRIFT: %s na VLAN %d (autorizado: %s)",
                    mac, node.vlan_id, sorted(allowed_vlans),
                )

    logger.info(
        "Detecção de VLAN Drift para %s: %d desvios encontrados.",
        customer_id, len(drifts),
    )
    return drifts


def _push_drift_incidents(
    customer_id: str,
    device_id: str,
    drifts: list[dict[str, Any]],
) -> int:
    """Persiste desvios de VLAN como incidentes. Retorna qtd criados."""
    count = 0
    for drift in drifts:
        category = (
            INCIDENT_CATEGORY_VLAN_DRIFT
            if drift["type"] == "vlan_drift"
            else INCIDENT_CATEGORY_UNAUTHORIZED_NODE
        )
        incident_id = incident_engine.push_incident(
            customer_id=customer_id,
            device_id=device_id,
            severity=drift["severity"],
            category=category,
            description=drift["description"],
            payload=drift,
        )
        if incident_id:
            count += 1
    return count


# ═══════════════════════════════════════════════════════════════════════════════
# Coleta de Topologia por dispositivo
# ═══════════════════════════════════════════════════════════════════════════════


def collect_topology_from_driver(
    customer_id: str,
    device_id: str,
    driver: NetworkDeviceDriver,
    snmp_community: str | None = None,
) -> dict[str, Any]:
    """
    Coleta ARP, MAC e LLDP de um dispositivo.

    Estratégia: CLI como primário, SNMP como fallback.

    Returns:
        Dict com chaves 'arp', 'mac', 'lldp' contendo as entradas coletadas.
    """
    result: dict[str, Any] = {"arp": [], "mac": [], "lldp": []}

    # ── ARP ────────────────────────────────────────────────────────────────
    try:
        result["arp"] = driver.get_arp_table()
        logger.info("[%s/%s] ARP via CLI: %d entradas.", customer_id, device_id, len(result["arp"]))
    except NotImplementedError:
        logger.debug("[%s/%s] Driver não suporta get_arp_table().", customer_id, device_id)
    except Exception as exc:
        logger.warning("[%s/%s] ARP via CLI falhou: %s", customer_id, device_id, exc)

    if not result["arp"] and snmp_community:
        try:
            result["arp"] = collect_arp_via_snmp(driver.host, snmp_community)
            logger.info("[%s/%s] ARP via SNMP: %d entradas.", customer_id, device_id, len(result["arp"]))
        except Exception as exc:
            logger.warning("[%s/%s] ARP via SNMP falhou: %s", customer_id, device_id, exc)

    # ── MAC ────────────────────────────────────────────────────────────────
    try:
        result["mac"] = driver.get_mac_table()
        logger.info("[%s/%s] MAC via CLI: %d entradas.", customer_id, device_id, len(result["mac"]))
    except NotImplementedError:
        logger.debug("[%s/%s] Driver não suporta get_mac_table().", customer_id, device_id)
    except Exception as exc:
        logger.warning("[%s/%s] MAC via CLI falhou: %s", customer_id, device_id, exc)

    if not result["mac"] and snmp_community:
        try:
            result["mac"] = collect_mac_via_snmp(driver.host, snmp_community)
            logger.info("[%s/%s] MAC via SNMP: %d entradas.", customer_id, device_id, len(result["mac"]))
        except Exception as exc:
            logger.warning("[%s/%s] MAC via SNMP falhou: %s", customer_id, device_id, exc)

    # ── LLDP ───────────────────────────────────────────────────────────────
    try:
        result["lldp"] = driver.get_lldp_neighbors()
        logger.info("[%s/%s] LLDP via CLI: %d vizinhos.", customer_id, device_id, len(result["lldp"]))
    except NotImplementedError:
        logger.debug("[%s/%s] Driver não suporta get_lldp_neighbors().", customer_id, device_id)
    except Exception as exc:
        logger.warning("[%s/%s] LLDP via CLI falhou: %s", customer_id, device_id, exc)

    if not result["lldp"] and snmp_community:
        try:
            result["lldp"] = collect_lldp_via_snmp(driver.host, snmp_community)
            logger.info("[%s/%s] LLDP via SNMP: %d vizinhos.", customer_id, device_id, len(result["lldp"]))
        except Exception as exc:
            logger.warning("[%s/%s] LLDP via SNMP falhou: %s", customer_id, device_id, exc)

    return result


# ═══════════════════════════════════════════════════════════════════════════════
# Orquestrador principal — scan de topologia completo
# ═══════════════════════════════════════════════════════════════════════════════


def run_topology_scan(
    customer_filter: str | None = None,
) -> dict[str, Any]:
    """
    Executa scan completo de topologia para todos os customers (ou filtrado).

    Fluxo:
        1. Lista dispositivos ativos do inventário.
        2. Para cada um, instancia o driver, conecta e coleta ARP/MAC/LLDP.
        3. Correlaciona L2/L3 → NetworkNode.
        4. Persiste no SQLite (entradas brutas + nós correlacionados).
        5. Detecta VLAN Drift e cria incidentes.

    Returns:
        Resumo: dispositivos escaneados, nós descobertos, drifts.
    """
    from drivers.mikrotik_driver import MikroTikDriver
    from utils.vault import (
        MasterKeyNotFoundError,
        VaultError,
        VaultManager,
    )

    logger.info("═══ Topology Scan iniciado ═══")

    # Carregar dispositivos e credenciais
    devices = list_active_inventory_devices()
    if customer_filter:
        devices = [d for d in devices if d.get("customer_id") == customer_filter]

    if not devices:
        logger.warning("Nenhum dispositivo ativo para topology scan.")
        return {"devices_scanned": 0, "nodes_discovered": 0, "drifts": 0}

    try:
        vault = VaultManager()
    except (MasterKeyNotFoundError, VaultError) as exc:
        logger.critical("VaultManager falhou: %s", exc)
        return {"devices_scanned": 0, "nodes_discovered": 0, "drifts": 0, "error": str(exc)}

    snmp_communities = load_snmp_communities()

    total_nodes = 0
    total_drifts = 0
    devices_ok = 0

    for dev in devices:
        customer_id = dev.get("customer_id", "?")
        device_id = dev.get("device_id", "?")
        vendor = dev.get("vendor", "").lower()
        host = dev.get("host", "")

        logger.info("── Topology scan: %s / %s ──", customer_id, device_id)

        # Obter credenciais
        try:
            creds = vault.get_credentials(customer_id, device_id)
        except Exception as exc:
            logger.error("[%s/%s] Credenciais não disponíveis: %s", customer_id, device_id, exc)
            continue

        # Instanciar driver
        if vendor == "mikrotik":
            driver = MikroTikDriver(
                host=creds["host"],
                username=creds["username"],
                password=creds["password"],
                port=int(creds.get("port", 22)),
            )
        else:
            logger.warning("[%s/%s] Vendor '%s' sem driver de topologia.", customer_id, device_id, vendor)
            continue

        snmp_community = snmp_communities.get((customer_id, device_id))

        try:
            with driver:
                raw_data = collect_topology_from_driver(
                    customer_id, device_id, driver, snmp_community,
                )
        except (ConnectionError, TimeoutError, OSError) as exc:
            logger.error("[%s/%s] Conexão falhou: %s", customer_id, device_id, exc)
            # Tentar coleta apenas via SNMP
            if snmp_community:
                logger.info("[%s/%s] Tentando coleta SNMP-only ...", customer_id, device_id)
                raw_data = {
                    "arp": collect_arp_via_snmp(host, snmp_community),
                    "mac": collect_mac_via_snmp(host, snmp_community),
                    "lldp": collect_lldp_via_snmp(host, snmp_community),
                }
            else:
                continue
        except Exception as exc:
            logger.exception("[%s/%s] Erro inesperado: %s", customer_id, device_id, exc)
            continue

        arp_list: list[ARPEntry] = raw_data["arp"]
        mac_list: list[MACEntry] = raw_data["mac"]
        lldp_list: list[LLDPNeighbor] = raw_data["lldp"]

        # Persistir entradas brutas
        insert_arp_entries(
            customer_id, device_id,
            [e.model_dump() for e in arp_list],
        )
        insert_mac_entries(
            customer_id, device_id,
            [e.model_dump() for e in mac_list],
        )
        insert_lldp_entries(
            customer_id, device_id,
            [e.model_dump() for e in lldp_list],
        )

        # Correlacionar L2/L3
        nodes = correlate_l2_l3(arp_list, mac_list)

        # Persistir nós correlacionados
        for node in nodes:
            upsert_node(
                customer_id=customer_id,
                device_id=device_id,
                mac_address=node.mac_address,
                ip_address=node.ip_address,
                hostname=node.hostname,
                vlan_id=node.vlan_id,
                switch_port=node.switch_port,
                vendor_oui=node.vendor_oui,
            )

        total_nodes += len(nodes)

        # Detectar VLAN Drift
        drifts = detect_vlan_drift(customer_id, nodes)
        if drifts:
            drift_count = _push_drift_incidents(customer_id, device_id, drifts)
            total_drifts += drift_count

        devices_ok += 1

    summary = {
        "devices_scanned": devices_ok,
        "nodes_discovered": total_nodes,
        "drifts": total_drifts,
    }
    logger.info(
        "═══ Topology Scan concluído — %d devices, %d nós, %d drifts ═══",
        devices_ok, total_nodes, total_drifts,
    )
    return summary


def get_topology_overview(customer_id: str) -> dict[str, Any]:
    """Retorna KPIs de topologia para um customer."""
    return {
        "total_nodes": count_nodes_by_customer(customer_id),
        "total_vlans": count_distinct_vlans(customer_id),
        "nodes": list_nodes(customer_id=customer_id),
    }
