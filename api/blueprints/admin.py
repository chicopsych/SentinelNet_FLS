"""
api/blueprints/admin.py
Blueprint de administração: incidentes órfãos.

Endpoints:
    GET  /admin/orphan-incidents       — lista
    POST /admin/orphan-incidents/purge — purge
"""

from __future__ import annotations

from flask import (
    Blueprint,
    current_app,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    url_for,
)

from api.http_utils import wants_json
from core.repositories.devices_repository import (
    list_inventory_devices,
)
from core.repositories.incidents_repository import (
    delete_orphan_incidents,
    list_orphan_incidents,
)
from internalloggin.logger import setup_logger

logger = setup_logger(__name__)

admin_bp = Blueprint("admin", __name__)


# ── Helpers ──────────────────────────────────────────


def _inventory_device_ids() -> set[str]:
    """device_ids presentes no inventário SQLite."""
    try:
        return {
            d["device_id"]
            for d in list_inventory_devices()
        }
    except Exception:
        return set()


def _check_admin_token(form_token: str) -> bool:
    """Valida token de admin submetido pelo form.

    Se API_STATIC_TOKEN não configurado, libera
    (modo dev).
    """
    cfg_token = current_app.config.get(
        "API_STATIC_TOKEN"
    )
    if not cfg_token:
        return True
    return form_token == cfg_token


# ── Rotas ────────────────────────────────────────────


@admin_bp.get("/orphan-incidents")
def list_orphans():
    """Lista incidentes órfãos para revisão."""
    device_ids = _inventory_device_ids()
    orphans = list_orphan_incidents(device_ids)

    if wants_json(request):
        return jsonify(
            {
                "orphan_count": len(orphans),
                "registered_devices": len(
                    device_ids
                ),
                "orphans": orphans,
            }
        )

    return render_template(
        "admin_orphans.html",
        orphans=orphans,
        count=len(orphans),
        registered_devices=len(device_ids),
    )


@admin_bp.post("/orphan-incidents/purge")
def purge_orphans():
    """Remove incidentes órfãos (com confirmação)."""
    form_token = request.form.get(
        "admin_token", ""
    ).strip()
    if not _check_admin_token(form_token):
        logger.warning(
            "Tentativa de purge de órfãos "
            "bloqueada: token admin inválido "
            "(origem: %s).",
            request.remote_addr,
        )
        flash(
            "Token de administrador inválido. "
            "Operação cancelada.",
            "danger",
        )
        return redirect(
            url_for("admin.list_orphans")
        )

    if request.form.get("confirm") != "yes":
        flash(
            "Confirmação não fornecida. Marque a "
            "caixa de confirmação.",
            "warning",
        )
        return redirect(
            url_for("admin.list_orphans")
        )

    device_ids = _inventory_device_ids()
    deleted = delete_orphan_incidents(device_ids)

    logger.info(
        "Admin purge: %d incidente(s) órfão(s) "
        "removido(s) — manual (origem: %s).",
        deleted,
        request.remote_addr,
    )

    if wants_json(request):
        return jsonify(
            {"deleted": deleted, "status": "ok"}
        )

    flash(
        f"{deleted} incidente(s) órfão(s) "
        "removido(s) com sucesso.",
        "success",
    )
    return redirect(url_for("admin.list_orphans"))
