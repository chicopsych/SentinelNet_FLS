"""
dashboard/blueprints/devices.py
Blueprint de visão de dispositivos monitorados.

Endpoints:
    GET /devices          — lista de dispositivos com status atual
    GET /devices/<device_id>  — detalhe de um dispositivo específico
"""

from flask import Blueprint, jsonify, render_template, request

devices_bp = Blueprint("devices", __name__)


# ── Helpers ────────────────────────────────────────────────────────────────────


def _list_devices(customer: str | None = None, vendor: str | None = None) -> list[dict]:
    """
    Retorna lista de dispositivos com estado atual.
    TODO: integrar com InventoryRepository e IncidentRepository.
    """
    return []


def _get_device(device_id: str) -> dict | None:
    """
    Retorna detalhes de um dispositivo pelo ID.
    TODO: integrar com InventoryRepository.
    """
    return None


# ── Rotas ──────────────────────────────────────────────────────────────────────


@devices_bp.get("/")
def list_devices():
    """Lista todos os dispositivos com filtros opcionais por cliente e vendor."""
    customer = request.args.get("customer")
    vendor = request.args.get("vendor")
    devices = _list_devices(customer=customer, vendor=vendor)
    return jsonify({"devices": devices, "total": len(devices)})


@devices_bp.get("/<device_id>")
def get_device(device_id: str):
    """Retorna estado e metadados de um dispositivo específico."""
    device = _get_device(device_id)
    if device is None:
        return jsonify({"error": f"Dispositivo '{device_id}' não encontrado."}), 404
    return jsonify(device)
