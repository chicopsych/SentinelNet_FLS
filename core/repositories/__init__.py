"""
core/repositories/
Camada de acesso a dados (DAL) do SentinelNet_FLS.

Repositórios compartilhados pelo CLI (main.py) e pela
camada web (api/).
"""

from core.repositories.credentials_repository import (
    save_device_credentials,
)
from core.repositories.devices_repository import (
    create_inventory_device,
    delete_inventory_device,
    ensure_inventory_table,
    get_inventory_device,
    list_active_inventory_devices,
    list_inventory_devices,
    set_inventory_device_active,
)
from core.repositories.incidents_repository import (
    count_by_status,
    count_open_by_severity,
    count_open_total,
    count_validated_today,
    delete_orphan_incidents,
    get_incident,
    list_distinct_open_devices,
    list_distinct_severities,
    list_distinct_statuses,
    list_incidents,
    list_open_summary_by_device,
    list_orphan_incidents,
    list_recent_open,
)

__all__ = [
    # credentials
    "save_device_credentials",
    # devices
    "create_inventory_device",
    "delete_inventory_device",
    "ensure_inventory_table",
    "get_inventory_device",
    "list_active_inventory_devices",
    "list_inventory_devices",
    "set_inventory_device_active",
    # incidents
    "count_by_status",
    "count_open_by_severity",
    "count_open_total",
    "count_validated_today",
    "delete_orphan_incidents",
    "get_incident",
    "list_distinct_open_devices",
    "list_distinct_severities",
    "list_distinct_statuses",
    "list_incidents",
    "list_open_summary_by_device",
    "list_orphan_incidents",
    "list_recent_open",
]
