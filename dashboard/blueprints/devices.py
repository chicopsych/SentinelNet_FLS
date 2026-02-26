"""
dashboard/blueprints/devices.py
Blueprint de visão de dispositivos monitorados.

Endpoints:
    GET /devices              — lista de dispositivos com status de saúde real
    GET /devices/<device_id>  — detalhe de um dispositivo específico
"""

from __future__ import annotations

import sqlite3
from typing import Any

from flask import Blueprint, flash, jsonify, render_template, request

from dashboard.common.constants import DB_PATH, OPEN_INCIDENT_STATUSES, RANK_TO_SEVERITY, SEVERITY_STATUS
from dashboard.common.db import db_exists
from dashboard.common.http import wants_json
from inventory.customer.customer import DEVICE_INVENTORY
from dashboard.services.discovery import DiscoveryError, run_nmap_discovery

devices_bp = Blueprint("devices", __name__)

# ── Helpers ────────────────────────────────────────────────────────────────────


def _incidents_by_device() -> dict[str, dict[str, Any]]:
    """
    Retorna un dict {device_id: {open_incidents, worst_severity, last_seen}}
    para todos os dispositivos com incidentes abertos.
    Retorna {} se o banco não existir.
    """
    if not db_exists():
        return {}

    placeholders = ",".join("?" * len(OPEN_INCIDENT_STATUSES))
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            f"""
            SELECT device_id,
                   COUNT(*)         AS open_incidents,
                   MAX(CASE severity
                       WHEN 'CRITICAL' THEN 5
                       WHEN 'HIGH'     THEN 4
                       WHEN 'MEDIUM'   THEN 3
                       WHEN 'WARNING'  THEN 2
                       WHEN 'LOW'      THEN 1
                       WHEN 'INFO'     THEN 0
                       ELSE 0 END)  AS sev_rank,
                   MAX(UPPER(severity)) AS worst_sev_raw,
                   MAX(timestamp)   AS last_seen
            FROM   incidents
            WHERE  status IN ({placeholders})
            GROUP  BY device_id
            """,
            tuple(OPEN_INCIDENT_STATUSES),
        ).fetchall()

    # Monta dict por device_id com a severidade mais alta em texto
    result: dict[str, dict[str, Any]] = {}
    for r in rows:
        device_id = r["device_id"]
        # Recalcula worst_severity como string
        worst_sev = RANK_TO_SEVERITY.get(r["sev_rank"], "INFO")
        result[device_id] = {
            "open_incidents": r["open_incidents"],
            "worst_severity": worst_sev,
            "status":         SEVERITY_STATUS.get(worst_sev, "info"),
            "last_seen":      r["last_seen"],
        }
    return result


def _list_devices(
    customer: str | None = None,
    vendor: str | None = None,
) -> list[dict]:
    """
    Mescla DEVICE_INVENTORY com dados de incidentes abertos do SQLite.
    Filtros opcionais por customer_id e vendor.
    """
    incidents = _incidents_by_device()
    devices: list[dict] = []

    for entry in DEVICE_INVENTORY:
        if customer and entry.get("customer_id", "").lower() != customer.lower():
            continue
        if vendor and entry.get("vendor", "").lower() != vendor.lower():
            continue

        device_id = entry["device_id"]
        inc_data = incidents.get(device_id, {})

        devices.append({
            "device_id":      device_id,
            "customer_id":    entry.get("customer_id", "—"),
            "vendor":         entry.get("vendor", "—"),
            "open_incidents": inc_data.get("open_incidents", 0),
            "worst_severity": inc_data.get("worst_severity", "—"),
            "status":         inc_data.get("status", "ok"),
            "last_seen":      inc_data.get("last_seen"),
        })

    return devices


def _get_device(device_id: str) -> dict | None:
    """Retorna dados de um dispositivo específico, ou None se não estiver no inventário."""
    entry = next(
        (d for d in DEVICE_INVENTORY if d["device_id"] == device_id), None
    )
    if entry is None:
        return None

    incidents = _incidents_by_device()
    inc_data  = incidents.get(device_id, {})
    return {
        "device_id":      device_id,
        "customer_id":    entry.get("customer_id", "—"),
        "vendor":         entry.get("vendor", "—"),
        "open_incidents": inc_data.get("open_incidents", 0),
        "worst_severity": inc_data.get("worst_severity", "—"),
        "status":         inc_data.get("status", "ok"),
        "last_seen":      inc_data.get("last_seen"),
    }


# ── Rotas ──────────────────────────────────────────────────────────────────────


@devices_bp.get("/")
def list_devices():
    """Lista todos os dispositivos com filtros opcionais por cliente e vendor."""
    customer = request.args.get("customer")
    vendor   = request.args.get("vendor")
    devices  = _list_devices(customer=customer, vendor=vendor)

    if wants_json(request):
        return jsonify({"devices": devices, "total": len(devices)})

    return render_template("devices.html", devices=devices, total=len(devices))


@devices_bp.route("/discover", methods=["GET", "POST"])
def discover_devices():
    """Executa discovery de ativos via nmap e exibe resultado para seleção."""
    network = request.values.get("network", "")
    discovery = None
    error_message = None

    if request.method == "POST":
        if not network.strip():
            error_message = "Informe uma faixa de rede em CIDR (ex: 192.168.88.0/24)."
        else:
            try:
                discovery = run_nmap_discovery(network)
            except DiscoveryError as exc:
                error_message = str(exc)

    if wants_json(request):
        if error_message:
            return jsonify({"error": error_message}), 400
        if discovery is None:
            return jsonify({
                "message": "Envie POST com campo 'network' para executar discovery.",
                "example": {"network": "192.168.88.0/24"},
            })
        return jsonify({
            "network": discovery.network,
            "scanned_at": discovery.scanned_at,
            "total_hosts": discovery.total_hosts,
            "hosts": discovery.hosts,
        })

    if error_message:
        flash(error_message, "danger")

    return render_template(
        "devices_discover.html",
        network=network,
        discovery=discovery,
    )


@devices_bp.get("/<device_id>")
def get_device(device_id: str):
    """Retorna estado e metadados de um dispositivo específico."""
    device = _get_device(device_id)
    if device is None:
        return jsonify({"error": f"Dispositivo '{device_id}' não encontrado."}), 404
    return jsonify(device)
