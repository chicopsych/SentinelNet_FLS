from __future__ import annotations

import json
from typing import Any

from dashboard.common.constants import OPEN_INCIDENT_STATUSES, RANK_TO_SEVERITY
from dashboard.common.db import get_connection, query_rows


STATUS_UI_MAP = {
    "new": "novo",
    "novo": "novo",
    "em_analise": "em_analise",
    "aprovado": "aprovado",
    "executado": "executado",
    "validado": "validado",
    "falhou": "falhou",
    "revertido": "revertido",
}


def normalize_status(status: str | None) -> str:
    if not status:
        return "novo"
    return STATUS_UI_MAP.get(str(status).strip().lower(), str(status).strip().lower())


def status_filter_values(status: str | None) -> list[str]:
    normalized = normalize_status(status)
    if normalized == "novo":
        return ["novo", "new"]
    return [normalized]


def normalize_diff_payload(payload: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return {"diff": {"modified": {}, "added": {}, "removed": {}, "firewall_audit": {}}, "vendor": "N/A", "site": "—"}

    vendor = payload.get("vendor", "N/A")
    site = payload.get("site", "—")

    if "diff" in payload and isinstance(payload.get("diff"), dict):
        diff = payload.get("diff", {})
    else:
        diff = {
            "modified": payload.get("modified", {}),
            "added": payload.get("added", {}),
            "removed": payload.get("removed", {}),
            "firewall_audit": payload.get("firewall_audit", {}),
        }

    if not isinstance(diff.get("modified"), dict):
        diff["modified"] = {}
    if not isinstance(diff.get("added"), dict):
        diff["added"] = {}
    if not isinstance(diff.get("removed"), dict):
        diff["removed"] = {}
    if not isinstance(diff.get("firewall_audit"), dict):
        diff["firewall_audit"] = {}

    return {
        **payload,
        "vendor": vendor,
        "site": site,
        "diff": diff,
    }


def row_to_incident_dict(row: Any) -> dict[str, Any]:
    data = dict(row)
    payload_raw: str | None = data.pop("payload_json", None)
    try:
        payload_obj: dict[str, Any] = json.loads(payload_raw) if payload_raw else {}
    except (json.JSONDecodeError, TypeError):
        payload_obj = {}
    diff_data = normalize_diff_payload(payload_obj)

    data["diff_data"] = diff_data
    data["device"] = data.get("device_id", "—")
    data["customer"] = data.get("customer_id", "—")
    data["type"] = data.get("category", "—")
    data["cause"] = data.get("description", "")
    data["detected_at"] = data.get("timestamp", "")
    data["vendor"] = diff_data.get("vendor", "N/A")
    data["site"] = diff_data.get("site", "—")
    data["status"] = normalize_status(data.get("status"))
    data.setdefault("remediation", None)
    data.setdefault("history", [])
    return data


def list_incidents(
    customer: str | None = None,
    device_id: str | None = None,
    vendor: str | None = None,
    severity: str | None = None,
    min_severity: str | None = None,
    status: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    sort: str = "newest",
    page: int = 1,
    page_size: int = 25,
) -> tuple[list[dict[str, Any]], int]:
    conn = get_connection()
    if conn is None:
        return [], 0

    try:
        conditions: list[str] = []
        params: list[Any] = []

        if customer:
            conditions.append("customer_id LIKE ?")
            params.append(f"%{customer}%")
        if device_id:
            conditions.append("device_id LIKE ?")
            params.append(f"%{device_id}%")
        if vendor:
            conditions.append("LOWER(COALESCE(payload_json, '')) LIKE ?")
            params.append(f"%{str(vendor).strip().lower()}%")
        if severity:
            conditions.append("severity = ?")
            params.append(severity.upper())
        if min_severity:
            severity_rank = {
                "INFO": 0,
                "LOW": 1,
                "WARNING": 2,
                "MEDIUM": 3,
                "HIGH": 4,
                "CRITICAL": 5,
            }
            min_rank = severity_rank.get(str(min_severity).strip().upper())
            if min_rank is not None:
                conditions.append(
                    """
                    (CASE UPPER(severity)
                        WHEN 'CRITICAL' THEN 5
                        WHEN 'HIGH' THEN 4
                        WHEN 'MEDIUM' THEN 3
                        WHEN 'WARNING' THEN 2
                        WHEN 'LOW' THEN 1
                        WHEN 'INFO' THEN 0
                        ELSE -1
                    END) >= ?
                    """
                )
                params.append(min_rank)
        if status:
            values = status_filter_values(status)
            placeholders = ",".join("?" for _ in values)
            conditions.append(f"LOWER(status) IN ({placeholders})")
            params.extend(values)
        if start_date:
            conditions.append("date(timestamp) >= date(?)")
            params.append(start_date)
        if end_date:
            conditions.append("date(timestamp) <= date(?)")
            params.append(end_date)

        where = ("WHERE " + " AND ".join(conditions)) if conditions else ""

        sort_clause_map = {
            "newest": "timestamp DESC, id DESC",
            "oldest": "timestamp ASC, id ASC",
            "severity_desc": "CASE UPPER(severity) WHEN 'CRITICAL' THEN 5 WHEN 'HIGH' THEN 4 WHEN 'MEDIUM' THEN 3 WHEN 'WARNING' THEN 2 WHEN 'LOW' THEN 1 WHEN 'INFO' THEN 0 ELSE -1 END DESC, timestamp DESC, id DESC",
            "severity_asc": "CASE UPPER(severity) WHEN 'CRITICAL' THEN 5 WHEN 'HIGH' THEN 4 WHEN 'MEDIUM' THEN 3 WHEN 'WARNING' THEN 2 WHEN 'LOW' THEN 1 WHEN 'INFO' THEN 0 ELSE -1 END ASC, timestamp DESC, id DESC",
        }
        order_by = sort_clause_map.get(sort, sort_clause_map["newest"])

        total: int = conn.execute(
            f"SELECT COUNT(*) FROM incidents {where}", params
        ).fetchone()[0]

        offset = (page - 1) * page_size
        rows = conn.execute(
            f"""
            SELECT id, timestamp, customer_id, device_id,
                   severity, category, description, payload_json, status
            FROM   incidents {where}
                 ORDER  BY {order_by}
            LIMIT  ? OFFSET ?
            """,
            [*params, page_size, offset],
        ).fetchall()

        return [row_to_incident_dict(row) for row in rows], total
    finally:
        conn.close()


def get_incident(incident_id: int) -> dict[str, Any] | None:
    conn = get_connection()
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
        return row_to_incident_dict(row) if row else None
    finally:
        conn.close()


def count_open_by_severity() -> dict[str, int]:
    placeholders = ",".join("?" * len(OPEN_INCIDENT_STATUSES))
    rows = query_rows(
        f"""
        SELECT UPPER(severity) AS sev, COUNT(*) AS cnt
        FROM   incidents
        WHERE  status IN ({placeholders})
        GROUP  BY UPPER(severity)
        """,
        tuple(OPEN_INCIDENT_STATUSES),
    )
    return {row["sev"]: row["cnt"] for row in rows}


def count_open_total() -> int:
    sev = count_open_by_severity()
    return sum(sev.values())


def list_distinct_open_devices() -> set[str]:
    placeholders = ",".join("?" * len(OPEN_INCIDENT_STATUSES))
    rows = query_rows(
        f"""
        SELECT DISTINCT device_id
        FROM incidents
        WHERE status IN ({placeholders})
        """,
        tuple(OPEN_INCIDENT_STATUSES),
    )
    return {row["device_id"] for row in rows}


def list_recent_open(limit: int = 5) -> list[dict[str, Any]]:
    placeholders = ",".join("?" * len(OPEN_INCIDENT_STATUSES))
    rows = query_rows(
        f"""
        SELECT id, timestamp, customer_id, device_id, severity, category, status
        FROM incidents
        WHERE status IN ({placeholders})
        ORDER BY timestamp DESC
        LIMIT ?
        """,
        tuple(OPEN_INCIDENT_STATUSES) + (limit,),
    )
    return [dict(row) for row in rows]


def count_by_status(status: str) -> int:
    rows = query_rows("SELECT COUNT(*) AS cnt FROM incidents WHERE status = ?", (status,))
    return rows[0]["cnt"] if rows else 0


def count_validated_today() -> int:
    rows = query_rows(
        """
        SELECT COUNT(*) AS cnt FROM incidents
        WHERE status = 'validado'
          AND date(timestamp) = date('now')
        """
    )
    return rows[0]["cnt"] if rows else 0


def list_open_summary_by_device() -> dict[str, dict[str, Any]]:
    placeholders = ",".join("?" * len(OPEN_INCIDENT_STATUSES))
    rows = query_rows(
        f"""
        SELECT device_id,
               COUNT(*) AS open_incidents,
               MAX(CASE severity
                   WHEN 'CRITICAL' THEN 5
                   WHEN 'HIGH'     THEN 4
                   WHEN 'MEDIUM'   THEN 3
                   WHEN 'WARNING'  THEN 2
                   WHEN 'LOW'      THEN 1
                   WHEN 'INFO'     THEN 0
                   ELSE 0 END) AS sev_rank,
               MAX(timestamp) AS last_seen
        FROM incidents
        WHERE status IN ({placeholders})
        GROUP BY device_id
        """,
        tuple(OPEN_INCIDENT_STATUSES),
    )

    result: dict[str, dict[str, Any]] = {}
    for row in rows:
        worst = RANK_TO_SEVERITY.get(row["sev_rank"], "INFO")
        result[row["device_id"]] = {
            "open_incidents": row["open_incidents"],
            "worst_severity": worst,
            "last_seen": row["last_seen"],
        }
    return result


def list_distinct_severities() -> list[str]:
    rows = query_rows(
        """
        SELECT DISTINCT UPPER(severity) AS sev
        FROM incidents
        WHERE severity IS NOT NULL
          AND TRIM(severity) <> ''
        """
    )
    values = [row["sev"] for row in rows if row["sev"]]

    rank = {
        "CRITICAL": 5,
        "HIGH": 4,
        "MEDIUM": 3,
        "WARNING": 2,
        "LOW": 1,
        "INFO": 0,
    }
    values.sort(key=lambda sev: rank.get(sev, -1), reverse=True)
    return values


def list_distinct_statuses() -> list[str]:
    rows = query_rows(
        """
        SELECT DISTINCT LOWER(status) AS st
        FROM incidents
        WHERE status IS NOT NULL
          AND TRIM(status) <> ''
        ORDER BY LOWER(status)
        """
    )
    return [row["st"] for row in rows if row["st"]]
