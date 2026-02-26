"""
dashboard/blueprints/incidents.py
Blueprint de gerenciamento de incidentes (drift e falhas).

Endpoints:
    GET  /incidents                — lista com filtros + paginação
    GET  /incidents/<int:id>       — detalhe completo + diff estruturado
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from flask import Blueprint, jsonify, render_template, request

incidents_bp = Blueprint("incidents", __name__)

# Caminho do banco SQLite — espelha o definido em IncidentEngine
_DB_PATH = Path(__file__).resolve().parent.parent.parent / "inventory" / "sentinel_data.db"


# ── Helpers internos ──────────────────────────────────────────────────────────


def _get_db() -> sqlite3.Connection | None:
    """Abre conexão row_factory ao banco de incidentes. Retorna None se não existir."""
    if not _DB_PATH.exists():
        return None
    conn = sqlite3.connect(_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    """
    Converte sqlite3.Row em dict compatível com os templates.
    Desserializa payload_json → diff_data e mapeia campos do banco
    para os aliases que os templates Jinja2 esperam.
    """
    d = dict(row)
    payload_raw: str | None = d.pop("payload_json", None)
    diff_data: dict[str, Any] = json.loads(payload_raw) if payload_raw else {}

    d["diff_data"]   = diff_data
    d["device"]      = d.get("device_id", "—")
    d["customer"]    = d.get("customer_id", "—")
    d["type"]        = d.get("category", "—")
    d["cause"]       = d.get("description", "")
    d["detected_at"] = d.get("timestamp", "")
    # vendor e site podem estar embutidos no payload
    d["vendor"]      = diff_data.get("vendor", "N/A")
    d["site"]        = diff_data.get("site", "—")
    # Campos opcionais esperados pelo template de detalhe
    d.setdefault("remediation", None)
    d.setdefault("history", [])
    return d


def _list_incidents(
    customer: str | None = None,
    severity: str | None = None,
    status: str | None = None,
    page: int = 1,
    page_size: int = 25,
) -> tuple[list[dict], int]:
    """
    Retorna (lista de incidentes, total) via queries reais ao SQLite.
    Suporta filtros opcionais por customer_id, severity e status,
    paginação e ordenação por timestamp decrescente.
    """
    conn = _get_db()
    if conn is None:
        return [], 0

    try:
        conditions: list[str] = []
        params: list[Any] = []

        if customer:
            conditions.append("customer_id LIKE ?")
            params.append(f"%{customer}%")
        if severity:
            conditions.append("severity = ?")
            params.append(severity.upper())
        if status:
            conditions.append("status = ?")
            params.append(status)

        where = ("WHERE " + " AND ".join(conditions)) if conditions else ""

        total: int = conn.execute(
            f"SELECT COUNT(*) FROM incidents {where}", params
        ).fetchone()[0]

        offset = (page - 1) * page_size
        rows = conn.execute(
            f"""
            SELECT id, timestamp, customer_id, device_id,
                   severity, category, description, payload_json, status
            FROM   incidents {where}
            ORDER  BY timestamp DESC
            LIMIT  ? OFFSET ?
            """,
            [*params, page_size, offset],
        ).fetchall()

        return [_row_to_dict(r) for r in rows], total
    finally:
        conn.close()


def _get_incident(incident_id: int) -> dict | None:
    """Retorna incidente completo com diff desserializado, ou None se não encontrado."""
    conn = _get_db()
    if conn is None:
        return None

    try:
        row = conn.execute(
            """
            SELECT id, timestamp, customer_id, device_id,
                   severity, category, description, payload_json, status
            FROM   incidents
            WHERE  id = ?
            """,
            (incident_id,),
        ).fetchone()
        return _row_to_dict(row) if row else None
    finally:
        conn.close()


# ── Rotas ──────────────────────────────────────────────────────────────────────


@incidents_bp.get("/")
def list_incidents():
    """
    Lista incidentes com filtros por cliente, severidade e status.
    Retorna HTML para navegador ou JSON para clientes de API.
    """
    customer = request.args.get("customer")
    severity = request.args.get("severity")
    status   = request.args.get("status")
    page     = max(1, int(request.args.get("page", 1)))

    incidents, total = _list_incidents(
        customer=customer,
        severity=severity,
        status=status,
        page=page,
    )

    if _wants_json():
        return jsonify({"incidents": incidents, "total": total, "page": page})

    return render_template(
        "incidents.html",
        incidents=incidents,
        total=total,
        page=page,
        filters={"customer": customer, "severity": severity, "status": status},
    )


@incidents_bp.get("/<int:incident_id>")
def get_incident(incident_id: int):
    """Detalhe do incidente: diff estruturado, metadados e severidade."""
    incident = _get_incident(incident_id)

    if incident is None:
        if _wants_json():
            return jsonify({"error": f"Incidente '{incident_id}' não encontrado."}), 404
        return render_template("404.html"), 404

    if _wants_json():
        return jsonify(incident)

    return render_template("incident_detail.html", incident=incident)


# ── Utilitários ───────────────────────────────────────────────────────────────


def _wants_json() -> bool:
    best = request.accept_mimetypes.best_match(["application/json", "text/html"])
    return best == "application/json"
