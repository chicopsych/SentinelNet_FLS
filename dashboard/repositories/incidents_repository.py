from __future__ import annotations

import json
from typing import Any

from dashboard.common.constants import OPEN_INCIDENT_STATUSES, RANK_TO_SEVERITY
from dashboard.common.db import get_connection, query_rows


def row_to_incident_dict(row: Any) -> dict[str, Any]:
    data = dict(row)
    payload_raw: str | None = data.pop("payload_json", None)
    diff_data: dict[str, Any] = json.loads(payload_raw) if payload_raw else {}

    data["diff_data"] = diff_data
    data["device"] = data.get("device_id", "—")
    data["customer"] = data.get("customer_id", "—")
    data["type"] = data.get("category", "—")
    data["cause"] = data.get("description", "")
    data["detected_at"] = data.get("timestamp", "")
    data["vendor"] = diff_data.get("vendor", "N/A")
    data["site"] = diff_data.get("site", "—")
    data.setdefault("remediation", None)
    data.setdefault("history", [])
    return data


def list_incidents(
    customer: str | None = None,
    severity: str | None = None,
    status: str | None = None,
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
