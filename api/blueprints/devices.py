"""
api/blueprints/devices.py
Blueprint de visão de dispositivos monitorados.

Endpoints:
    GET  /devices/             — lista com status
    GET  /devices/<device_id>  — detalhe
    GET  /devices/discover     — discovery nmap
    POST /devices/discover     — executa discovery
    GET  /devices/onboard      — form cadastro
    POST /devices/onboard      — persiste dispositivo
    POST /devices/toggle-active — ativa/desativa
"""

from __future__ import annotations

from flask import (
    Blueprint,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    url_for,
)

from api.http_utils import wants_json
from core.repositories.credentials_repository import (
    save_device_credentials,
)
from core.repositories.devices_repository import (
    create_inventory_device,
    delete_inventory_device,
    get_inventory_device,
    set_inventory_device_active,
)
from core.services.device_service import (
    get_device_detail,
    get_devices_with_status,
)
from core.services.discovery_service import (
    DiscoveryError,
    ScanOptions,
    run_nmap_discovery,
)

devices_bp = Blueprint("devices", __name__)


# ── Helpers ──────────────────────────────────────────


def _parse_port(value: str, default: int = 22) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


# ── Rotas ────────────────────────────────────────────


@devices_bp.get("/")
def list_devices():
    """Lista dispositivos com filtros opcionais."""
    customer = request.args.get("customer")
    vendor = request.args.get("vendor")
    devices = get_devices_with_status(
        customer=customer, vendor=vendor
    )

    if wants_json(request):
        return jsonify(
            {"devices": devices, "total": len(devices)}
        )

    return render_template(
        "devices.html",
        devices=devices,
        total=len(devices),
    )


@devices_bp.route(
    "/discover", methods=["GET", "POST"]
)
def discover_devices():
    """Discovery de ativos via nmap."""
    network = request.values.get("network", "")
    discovery = None
    error_message = None

    if request.method == "POST":
        if not network.strip():
            error_message = (
                "Informe uma faixa de rede em CIDR "
                "(ex: 192.168.88.0/24)."
            )
        else:
            form = request.form
            opts = ScanOptions(
                ports_fast=bool(
                    form.get("ports_fast")
                ),
                ports_extended=bool(
                    form.get("ports_extended")
                ),
                os_detection=bool(
                    form.get("os_detection")
                ),
                service_version=bool(
                    form.get("service_version")
                ),
            )
            try:
                discovery = run_nmap_discovery(
                    network, options=opts
                )
            except DiscoveryError as exc:
                error_message = str(exc)

    if wants_json(request):
        if error_message:
            return (
                jsonify({"error": error_message}),
                400,
            )
        if discovery is None:
            return jsonify(
                {
                    "message": (
                        "Envie POST com campo "
                        "'network' para executar "
                        "discovery."
                    ),
                    "example": {
                        "network": "192.168.88.0/24"
                    },
                }
            )
        return jsonify(
            {
                "network": discovery.network,
                "scanned_at": discovery.scanned_at,
                "total_hosts": discovery.total_hosts,
                "hosts": discovery.hosts,
            }
        )

    if error_message:
        flash(error_message, "danger")

    return render_template(
        "devices_discover.html",
        network=network,
        discovery=discovery,
    )


@devices_bp.route(
    "/onboard", methods=["GET", "POST"]
)
def onboard_device():
    """Cadastro manual de dispositivo."""
    form_data = {
        "customer": request.values.get(
            "customer", ""
        ),
        "device": request.values.get("device", ""),
        "vendor": request.values.get("vendor", ""),
        "host": request.values.get("host", ""),
        "porta": request.values.get("porta", "22"),
        "username": request.values.get(
            "username", ""
        ),
        "token": request.values.get("token", ""),
        "snmp_community": request.values.get(
            "snmp_community", ""
        ),
    }

    if request.method == "POST":
        customer = form_data["customer"].strip()
        device = form_data["device"].strip()
        vendor = form_data["vendor"].strip()
        host = form_data["host"].strip()
        port = _parse_port(
            form_data["porta"], default=-1
        )
        username = form_data["username"].strip()
        password = request.form.get("password", "")
        token = (
            form_data["token"].strip() or None
        )
        snmp_community = (
            form_data["snmp_community"].strip()
            or None
        )

        ok, message = create_inventory_device(
            customer_id=customer,
            device_id=device,
            vendor=vendor,
            host=host,
            port=port,
        )
        if ok:
            cred_ok, cred_msg = (
                save_device_credentials(
                    customer_id=customer,
                    device_id=device,
                    host=host,
                    username=username,
                    password=password,
                    port=port,
                    token=token,
                    snmp_community=snmp_community,
                )
            )

            if not cred_ok:
                delete_inventory_device(
                    customer_id=customer,
                    device_id=device,
                )
                flash(
                    f"{cred_msg} Cadastro do "
                    "dispositivo revertido.",
                    "danger",
                )
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
                        "snmp_community": "",
                    },
                )

        flash(message, "danger")

    if wants_json(request):
        return jsonify(
            {
                "message": (
                    "Use POST para cadastrar "
                    "dispositivo."
                ),
                "form": form_data,
            }
        )

    return render_template(
        "devices_onboard.html", form=form_data
    )


@devices_bp.post("/toggle-active")
def toggle_device_active():
    """Ativa/desativa dispositivo no inventário."""
    customer_id = request.form.get(
        "customer_id", ""
    ).strip()
    device_id = request.form.get(
        "device_id", ""
    ).strip()
    active_raw = request.form.get(
        "active", "1"
    ).strip()
    active = active_raw == "1"
    customer_filter = request.form.get(
        "customer_filter", ""
    ).strip()
    vendor_filter = request.form.get(
        "vendor_filter", ""
    ).strip()

    if not customer_id or not device_id:
        flash(
            "Identificação de dispositivo "
            "inválida para alteração de status.",
            "danger",
        )
        return redirect(
            url_for(
                "devices.list_devices",
                customer=customer_filter,
                vendor=vendor_filter,
            )
        )

    existing = get_inventory_device(
        customer_id=customer_id,
        device_id=device_id,
    )
    if existing is None:
        flash(
            "Dispositivo não encontrado no "
            "inventário persistido.",
            "danger",
        )
        return redirect(
            url_for(
                "devices.list_devices",
                customer=customer_filter,
                vendor=vendor_filter,
            )
        )

    ok, message = set_inventory_device_active(
        customer_id=customer_id,
        device_id=device_id,
        active=active,
    )

    flash(message, "success" if ok else "danger")

    if wants_json(request):
        status_code = 200 if ok else 404
        return (
            jsonify({"ok": ok, "message": message}),
            status_code,
        )

    return redirect(
        url_for(
            "devices.list_devices",
            customer=customer_filter,
            vendor=vendor_filter,
        )
    )


@devices_bp.get("/<device_id>")
def get_device(device_id: str):
    """Estado e metadados de um dispositivo."""
    device = get_device_detail(device_id)
    if device is None:
        return (
            jsonify(
                {
                    "error": (
                        f"Dispositivo '{device_id}'"
                        " não encontrado."
                    )
                }
            ),
            404,
        )
    return jsonify(device)
