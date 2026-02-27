"""
core/services/overview_service.py
KPIs consolidados do ambiente monitorado.

Orquestra repositórios e reachability para produzir o
payload de dados do painel executivo.
"""

from __future__ import annotations

from typing import Any

from core.repositories.devices_repository import (
    ensure_inventory_table,
    list_active_inventory_devices,
    list_inventory_devices,
)
from core.repositories.incidents_repository import (
    count_by_status,
    count_open_by_severity,
    count_validated_today,
    delete_orphan_incidents,
    list_distinct_open_devices,
    list_recent_open,
)
from core.services.reachability_service import (
    check_device_reachability,
    load_snmp_communities,
)


def get_overview_data() -> dict[str, Any]:
    """
    Monta os KPIs consolidados consultando o SQLite.

    Fontes:
      - inventory_devices → total_devices
      - incidents → contagens por severidade / status
    """
    # 1. Inventário persistido
    ensure_inventory_table()
    inventory_entries = list_inventory_devices()
    inventory_ids = {
        e.get("device_id")
        for e in inventory_entries
        if e.get("device_id")
    }
    active_entries = list_active_inventory_devices()
    active_ids = {
        e.get("device_id")
        for e in active_entries
        if e.get("device_id")
    }

    # 2. Limpeza de incidentes órfãos
    delete_orphan_incidents(inventory_ids)

    # 3. Contagem de incidentes abertos
    severity_counts = count_open_by_severity()
    total_open = sum(severity_counts.values())

    # 4. Dispositivos ativos com incidente aberto
    open_devices = (
        list_distinct_open_devices()
        if total_open > 0
        else set()
    )
    devices_with_incident = set(
        open_devices
    ).intersection(active_ids)

    # 5. Reachability por ping/SNMP
    snmp_map = load_snmp_communities()
    warning_devices: set[str] = set()
    for entry in active_entries:
        device_id = entry.get("device_id")
        if not device_id:
            continue
        snmp_community = snmp_map.get(
            (entry.get("customer_id"), device_id)
        )
        reachability = check_device_reachability(
            host=entry.get("host", ""),
            snmp_community=snmp_community,
        )
        if reachability.get("warning"):
            warning_devices.add(device_id)

    total_devices = len(active_entries)
    with_incident = len(devices_with_incident)
    unhealthy = devices_with_incident.union(
        warning_devices
    )
    healthy = total_devices - len(unhealthy)

    recent_incidents = list_recent_open(limit=5)

    # Remediações (placeholder)
    pending_approval = count_by_status("aprovado")
    executed_today = count_validated_today()
    failed = count_by_status("falhou")

    return {
        "devices": {
            "total": total_devices,
            "healthy": max(healthy, 0),
            "with_incident": with_incident,
            "warning": len(warning_devices),
        },
        "incidents": {
            "open": total_open,
            "critical": severity_counts.get(
                "CRITICAL", 0
            ),
            "high": severity_counts.get("HIGH", 0),
            "warning": severity_counts.get(
                "WARNING", 0
            ),
            "info": severity_counts.get("INFO", 0),
        },
        "remediation": {
            "pending_approval": pending_approval,
            "executed_today": executed_today,
            "failed": failed,
        },
        "slo": {
            "mtta_minutes": None,
            "mttr_minutes": None,
        },
        "recent_incidents": recent_incidents,
    }
