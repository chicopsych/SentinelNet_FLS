"""
dashboard/blueprints/devices.py
Blueprint de visão de dispositivos monitorados.

Endpoints:
    GET /devices              — lista de dispositivos com status de saúde real
    GET /devices/<device_id>  — detalhe de um dispositivo específico
    POST /devices/toggle-active — ativa/desativa dispositivo no inventário persistido
"""

from __future__ import annotations

from typing import Any

from flask import Blueprint, flash, jsonify, redirect, render_template, request, url_for

from dashboard.common.constants import SEVERITY_STATUS
from dashboard.common.http import wants_json
from dashboard.repositories.credentials_repository import save_device_credentials
from dashboard.repositories.devices_repository import (
    create_inventory_device,
    delete_inventory_device,
    ensure_inventory_table,
    get_inventory_device,
    list_inventory_devices,
    set_inventory_device_active,
)
from dashboard.repositories.incidents_repository import list_open_summary_by_device
from dashboard.services.discovery import DiscoveryError, run_nmap_discovery

devices_bp = Blueprint("devices", __name__)

# ── Helpers ────────────────────────────────────────────────────────────────────


def _incidents_by_device() -> dict[str, dict[str, Any]]:
    """
    Retorna un dict {device_id: {open_incidents, worst_severity, last_seen}}
    para todos os dispositivos com incidentes abertos.
    Retorna {} se o banco não existir.
    """
    raw = list_open_summary_by_device()
    result: dict[str, dict[str, Any]] = {}
    for device_id, payload in raw.items():
        worst_sev = payload.get("worst_severity", "INFO")
        result[device_id] = {
            "open_incidents": payload.get("open_incidents", 0),
            "worst_severity": worst_sev,
            "status": SEVERITY_STATUS.get(worst_sev, "info"),
            "last_seen": payload.get("last_seen"),
        }
    return result


def _list_devices(
    customer: str | None = None,
    vendor: str | None = None,
) -> list[dict]:
    """
    Lista inventário persistido no SQLite com dados de incidentes abertos.
    Filtros opcionais por customer_id e vendor.
    """
    incidents = _incidents_by_device()
    devices: list[dict] = []

    ensure_inventory_table()
    persisted_entries = list_inventory_devices()

    for entry in persisted_entries:
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
            "active":         bool(entry.get("active", 1)),
        })

    return devices


def _parse_port(value: str, default: int = 22) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _get_device(device_id: str) -> dict | None:
    """Retorna dados de um dispositivo específico, ou None se não estiver no inventário."""
    entry = next((d for d in list_inventory_devices() if d["device_id"] == device_id), None)
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
        "active":         bool(entry.get("active", 1)),
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


@devices_bp.route("/onboard", methods=["GET", "POST"])
def onboard_device():
    """Cadastro manual de dispositivo com persistência no SQLite."""
    form_data = {
        "customer": request.values.get("customer", ""),
        "device": request.values.get("device", ""),
        "vendor": request.values.get("vendor", ""),
        "host": request.values.get("host", ""),
        "porta": request.values.get("porta", "22"),
        "username": request.values.get("username", ""),
        "token": request.values.get("token", ""),
    }

    if request.method == "POST":
        customer = form_data["customer"].strip()
        device = form_data["device"].strip()
        vendor = form_data["vendor"].strip()
        host = form_data["host"].strip()
        port = _parse_port(form_data["porta"], default=-1)
        username = form_data["username"].strip()
        password = request.form.get("password", "")
        token = form_data["token"].strip() or None

        ok, message = create_inventory_device(
            customer_id=customer,
            device_id=device,
            vendor=vendor,
            host=host,
            port=port,
        )
        if ok:
            cred_ok, cred_msg = save_device_credentials(
                customer_id=customer,
                device_id=device,
                host=host,
                username=username,
                password=password,
                port=port,
                token=token,
            )

            if not cred_ok:
                delete_inventory_device(customer_id=customer, device_id=device)
                flash(f"{cred_msg} Cadastro do dispositivo revertido.", "danger")
            else:
                flash(message, "success")
                flash(cred_msg, "info")
                return render_template(
                    "devices_onboard.html",
                    form={
                        "customer": "",
                        "device": "",
                        "vendor": "",
                        "host": "",
                        "porta": "22",
                        "username": "",
                        "token": "",
                    },
                )

        flash(message, "danger")

    if wants_json(request):
        return jsonify({"message": "Use POST para cadastrar dispositivo.", "form": form_data})

    return render_template("devices_onboard.html", form=form_data)


@devices_bp.post("/toggle-active")
def toggle_device_active():
    """Ativa/desativa dispositivo persistido no inventário SQLite."""
    customer_id = request.form.get("customer_id", "").strip()
    device_id = request.form.get("device_id", "").strip()
    active_raw = request.form.get("active", "1").strip()
    active = active_raw == "1"
    customer_filter = request.form.get("customer_filter", "").strip()
    vendor_filter = request.form.get("vendor_filter", "").strip()

    if not customer_id or not device_id:
        flash("Identificação de dispositivo inválida para alteração de status.", "danger")
        return redirect(url_for("devices.list_devices", customer=customer_filter, vendor=vendor_filter))

    existing = get_inventory_device(customer_id=customer_id, device_id=device_id)
    if existing is None:
        flash("Dispositivo não encontrado no inventário persistido.", "danger")
        return redirect(url_for("devices.list_devices", customer=customer_filter, vendor=vendor_filter))

    ok, message = set_inventory_device_active(
        customer_id=customer_id,
        device_id=device_id,
        active=active,
    )

    flash(message, "success" if ok else "danger")

    if wants_json(request):
        status_code = 200 if ok else 404
        return jsonify({"ok": ok, "message": message}), status_code

    return redirect(url_for("devices.list_devices", customer=customer_filter, vendor=vendor_filter))


@devices_bp.get("/<device_id>")
def get_device(device_id: str):
    """Retorna estado e metadados de um dispositivo específico."""
    device = _get_device(device_id)
    if device is None:
        return jsonify({"error": f"Dispositivo '{device_id}' não encontrado."}), 404
    return jsonify(device)
