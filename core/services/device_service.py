"""
core/services/device_service.py
Correlação dispositivo ↔ incidente e reachability.

Fornece dados consolidados de dispositivos para
qualquer interface (CLI ou Web).
"""

from __future__ import annotations

from typing import Any

from core.constants import SEVERITY_STATUS
from core.repositories.devices_repository import (
    ensure_inventory_table,
    list_inventory_devices,
)
from core.repositories.incidents_repository import (
    list_open_summary_by_device,
)
from core.services.audit_service import load_baseline
from core.services.reachability_service import (
    check_device_reachability,
    load_snmp_communities,
)


def _incidents_by_device() -> dict[str, dict[str, Any]]:
    """
    {device_id: {open_incidents, worst_severity, …}}
    para dispositivos com incidentes abertos.
    """
    raw = list_open_summary_by_device()
    result: dict[str, dict[str, Any]] = {}
    for device_id, payload in raw.items():
        worst_sev = payload.get("worst_severity", "INFO")
        result[device_id] = {
            "open_incidents": payload.get(
                "open_incidents", 0
            ),
            "worst_severity": worst_sev,
            "status": SEVERITY_STATUS.get(
                worst_sev, "info"
            ),
            "last_seen": payload.get("last_seen"),
        }
    return result


def get_devices_with_status(
    customer: str | None = None,
    vendor: str | None = None,
) -> list[dict[str, Any]]:
    """
    Inventário SQLite enriquecido com incidentes e
    reachability. Filtros opcionais por customer / vendor.
    """
    incidents = _incidents_by_device()
    devices: list[dict[str, Any]] = []
    snmp_map = load_snmp_communities()

    ensure_inventory_table()
    persisted = list_inventory_devices()

    for entry in persisted:
        cid = entry.get("customer_id", "")
        if customer and cid.lower() != customer.lower():
            continue
        if (
            vendor
            and entry.get("vendor", "").lower()
            != vendor.lower()
        ):
            continue

        device_id = entry["device_id"]
        inc = incidents.get(device_id, {})
        status = inc.get("status", "ok")

        if entry.get("active", 1):
            snmp_community = snmp_map.get(
                (cid, device_id)
            )
            reach = check_device_reachability(
                host=entry.get("host", ""),
                snmp_community=snmp_community,
            )
            if status == "ok" and reach.get("warning"):
                status = "warning"
        else:
            reach = {
                "ping_ok": None,
                "snmp_ok": None,
                "warning": False,
            }

        bl = load_baseline(cid, device_id)
        devices.append(
            {
                "device_id": device_id,
                "customer_id": cid or "—",
                "vendor": entry.get("vendor", "—"),
                "open_incidents": inc.get(
                    "open_incidents", 0
                ),
                "worst_severity": inc.get(
                    "worst_severity", "—"
                ),
                "status": status,
                "last_seen": inc.get("last_seen"),
                "active": bool(entry.get("active", 1)),
                "ping_ok": reach.get("ping_ok"),
                "snmp_ok": reach.get("snmp_ok"),
                "has_baseline": bl is not None,
                "baseline_at": (
                    bl.collected_at.isoformat()
                    if bl is not None
                    else None
                ),
            }
        )

    return devices


def get_device_detail(
    device_id: str,
) -> dict[str, Any] | None:
    """Dados consolidados de um único dispositivo."""
    entry = next(
        (
            d
            for d in list_inventory_devices()
            if d["device_id"] == device_id
        ),
        None,
    )
    if entry is None:
        return None

    incidents = _incidents_by_device()
    inc = incidents.get(device_id, {})
    status = inc.get("status", "ok")
    snmp_map = load_snmp_communities()

    if entry.get("active", 1):
        snmp_community = snmp_map.get(
            (entry.get("customer_id"), device_id)
        )
        reach = check_device_reachability(
            host=entry.get("host", ""),
            snmp_community=snmp_community,
        )
        if status == "ok" and reach.get("warning"):
            status = "warning"
    else:
        reach = {
            "ping_ok": None,
            "snmp_ok": None,
            "warning": False,
        }

    customer_id = entry.get("customer_id", "")
    bl = load_baseline(customer_id, device_id)
    return {
        "device_id": device_id,
        "customer_id": customer_id or "—",
        "vendor": entry.get("vendor", "—"),
        "open_incidents": inc.get(
            "open_incidents", 0
        ),
        "worst_severity": inc.get(
            "worst_severity", "—"
        ),
        "status": status,
        "last_seen": inc.get("last_seen"),
        "active": bool(entry.get("active", 1)),
        "ping_ok": reach.get("ping_ok"),
        "snmp_ok": reach.get("snmp_ok"),
        "has_baseline": bl is not None,
        "baseline_at": (
            bl.collected_at.isoformat()
            if bl is not None
            else None
        ),
    }
