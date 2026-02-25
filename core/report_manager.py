"""
core/report_manager.py
──────────────────────
Gerenciador de persistência de relatórios de auditoria.

Responsável por salvar ``AuditReport`` em três formatos complementares:

1. **JSON** — arquivo estruturado e versionável, organizado por
   ``logs/reports/<customer>/<device>/<timestamp>.json``.

2. **HTML** — relatório visual renderizado via Jinja2, entregável ao
   cliente ou stakeholder para evidência de auditoria.

3. **SQLite** — banco de dados histórico para consultas de tendência,
   reincidência e dashboards operacionais.

Design Decisions
────────────────
1. Diretório hierárquico por cliente/device:
   Facilita navegação manual, integração com Git (versionamento de
   evidências) e limpeza seletiva por cliente.

2. Timestamp ISO 8601 compacto no nome do arquivo:
   Formato ``YYYYMMDD_HHMMSS`` evita conflitos e permite ordenação
   cronológica por nome.

3. SQLite com JSON embutido:
   A coluna ``drift_data_json`` armazena o ``DiffReport`` completo
   como TEXT (JSON serializado). Isso permite consultas simples por
   severidade/data sem perder a rastreabilidade dos campos detalhados.

4. ``persist()`` salva nos três formatos de uma vez:
   Garante consistência — se o JSON foi salvo, o HTML e o SQLite
   também foram. Erros em formatos individuais são logados mas não
   interrompem os demais (fail-safe).

5. Sem Jinja2 como hard dependency:
   Se Jinja2 não estiver instalado, o HTML é gerado com template
   string nativo do Python (f-string). Isso permite uso mínimo sem
   instalar pacotes extras, embora o resultado visual seja mais simples.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from core.audit_report import AuditReport, Severity
from internalloggin.logger import setup_logger

logger = setup_logger("ReportManager")

# ─── Constantes ───────────────────────────────────────────────────────────────

_DEFAULT_REPORTS_DIR = Path("logs/reports")
_DEFAULT_DB_PATH = Path("logs/audit_history.db")
_TIMESTAMP_FMT = "%Y%m%d_%H%M%S"

# ─── DDL do SQLite ────────────────────────────────────────────────────────────

_CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS audit_reports (
    audit_id            TEXT PRIMARY KEY,
    customer_id         TEXT NOT NULL,
    device_id           TEXT NOT NULL,
    hostname            TEXT NOT NULL,
    severity            INTEGER NOT NULL,
    severity_label      TEXT NOT NULL,
    audit_timestamp     TEXT NOT NULL,
    drift_summary       TEXT NOT NULL,
    drift_data_json     TEXT NOT NULL,
    baseline_collected   TEXT,
    current_collected    TEXT,
    created_at          TEXT NOT NULL DEFAULT (datetime('now'))
);
"""

_CREATE_INDEX_SQL = [
    "CREATE INDEX IF NOT EXISTS idx_customer ON audit_reports(customer_id);",
    "CREATE INDEX IF NOT EXISTS idx_device ON audit_reports(customer_id, device_id);",
    "CREATE INDEX IF NOT EXISTS idx_severity ON audit_reports(severity);",
    "CREATE INDEX IF NOT EXISTS idx_timestamp ON audit_reports(audit_timestamp);",
]


class ReportManager:
    """
    Gerencia persistência de relatórios de auditoria em JSON, HTML e SQLite.

    Uso típico::

        manager = ReportManager()
        audit = AuditReport.from_diff_report(report, "cliente_a", "borda-01", "borda-01")
        paths = manager.persist(audit)
        # paths == {"json": Path(...), "html": Path(...), "db": Path(...)}

    Args:
        reports_dir: Diretório base para arquivos JSON/HTML.
                     Default: ``logs/reports/``.
        db_path:     Caminho do banco SQLite.
                     Default: ``logs/audit_history.db``.
    """

    def __init__(
        self,
        reports_dir: Optional[Path | str] = None,
        db_path: Optional[Path | str] = None,
    ) -> None:
        self._reports_dir = Path(reports_dir) if reports_dir else _DEFAULT_REPORTS_DIR
        self._db_path = Path(db_path) if db_path else _DEFAULT_DB_PATH

        # Garante que os diretórios necessários existem
        self._reports_dir.mkdir(parents=True, exist_ok=True)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)

        # Inicializa o banco SQLite
        self._init_db()

        logger.info(
            "ReportManager inicializado — reports_dir='%s', db='%s'",
            self._reports_dir, self._db_path,
        )

    # ── API Pública ───────────────────────────────────────────────────────────

    def persist(self, audit: AuditReport) -> dict[str, Path]:
        """
        Salva o relatório nos três formatos (JSON, HTML, SQLite).

        Cada formato é salvo de forma independente; falha em um não
        impede a persistência nos demais.

        Args:
            audit: Relatório de auditoria a ser persistido.

        Returns:
            Dicionário com os caminhos dos arquivos gerados::

                {"json": Path(...), "html": Path(...), "db": Path(...)}
        """
        paths: dict[str, Path] = {}

        # ── JSON ──────────────────────────────────────────────────────────
        try:
            json_path = self._save_json(audit)
            paths["json"] = json_path
            logger.info("Relatório JSON salvo: %s", json_path)
        except Exception as exc:
            logger.error("Falha ao salvar JSON: %s", exc)

        # ── HTML ──────────────────────────────────────────────────────────
        try:
            html_path = self._save_html(audit)
            paths["html"] = html_path
            logger.info("Relatório HTML salvo: %s", html_path)
        except Exception as exc:
            logger.error("Falha ao salvar HTML: %s", exc)

        # ── SQLite ────────────────────────────────────────────────────────
        try:
            self._save_to_db(audit)
            paths["db"] = self._db_path
            logger.info("Relatório persistido no SQLite: %s", self._db_path)
        except Exception as exc:
            logger.error("Falha ao salvar no SQLite: %s", exc)

        return paths

    def load_history(
        self,
        customer_id: Optional[str] = None,
        device_id: Optional[str] = None,
        severity_min: Optional[Severity] = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """
        Consulta o histórico de auditorias no banco SQLite.

        Permite filtrar por cliente, dispositivo e severidade mínima.
        Resultados são ordenados por timestamp decrescente (mais recente
        primeiro).

        Args:
            customer_id: Filtrar por cliente (opcional).
            device_id: Filtrar por dispositivo — requer customer_id (opcional).
            severity_min: Severidade mínima para incluir no resultado (opcional).
            limit: Número máximo de registros retornados. Default: 50.

        Returns:
            Lista de dicionários com os campos do relatório.
        """
        query = "SELECT * FROM audit_reports WHERE 1=1"
        params: list[Any] = []

        if customer_id:
            query += " AND customer_id = ?"
            params.append(customer_id)
        if device_id:
            query += " AND device_id = ?"
            params.append(device_id)
        if severity_min is not None:
            query += " AND severity >= ?"
            params.append(int(severity_min))

        query += " ORDER BY audit_timestamp DESC LIMIT ?"
        params.append(limit)

        try:
            with sqlite3.connect(str(self._db_path)) as conn:
                conn.row_factory = sqlite3.Row
                rows = conn.execute(query, params).fetchall()
                return [dict(row) for row in rows]
        except sqlite3.Error as exc:
            logger.error("Falha ao consultar histórico: %s", exc)
            return []

    def get_stats(
        self,
        customer_id: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        Retorna estatísticas agregadas do histórico de auditorias.

        Args:
            customer_id: Filtrar por cliente (opcional).

        Returns:
            Dicionário com contagens por severidade e total de auditorias.
        """
        query = """
            SELECT
                COUNT(*) AS total,
                SUM(CASE WHEN severity = 0 THEN 1 ELSE 0 END) AS compliant,
                SUM(CASE WHEN severity = 1 THEN 1 ELSE 0 END) AS low,
                SUM(CASE WHEN severity = 2 THEN 1 ELSE 0 END) AS medium,
                SUM(CASE WHEN severity = 3 THEN 1 ELSE 0 END) AS high,
                SUM(CASE WHEN severity = 4 THEN 1 ELSE 0 END) AS critical
            FROM audit_reports
        """
        params: list[Any] = []

        if customer_id:
            query += " WHERE customer_id = ?"
            params.append(customer_id)

        try:
            with sqlite3.connect(str(self._db_path)) as conn:
                row = conn.execute(query, params).fetchone()
                if row:
                    return {
                        "total": row[0],
                        "compliant": row[1],
                        "low": row[2],
                        "medium": row[3],
                        "high": row[4],
                        "critical": row[5],
                    }
        except sqlite3.Error as exc:
            logger.error("Falha ao obter estatísticas: %s", exc)

        return {"total": 0, "compliant": 0, "low": 0, "medium": 0, "high": 0, "critical": 0}

    # ── Internals ─────────────────────────────────────────────────────────────

    def _init_db(self) -> None:
        """Cria a tabela e índices no SQLite se não existirem."""
        try:
            with sqlite3.connect(str(self._db_path)) as conn:
                conn.execute(_CREATE_TABLE_SQL)
                for idx_sql in _CREATE_INDEX_SQL:
                    conn.execute(idx_sql)
                conn.commit()
            logger.debug("SQLite inicializado: %s", self._db_path)
        except sqlite3.Error as exc:
            logger.error("Falha ao inicializar SQLite: %s", exc)

    def _build_device_dir(self, audit: AuditReport) -> Path:
        """Constrói o diretório hierárquico para o dispositivo."""
        device_dir = self._reports_dir / audit.customer_id / audit.device_id
        device_dir.mkdir(parents=True, exist_ok=True)
        return device_dir

    def _build_filename(self, audit: AuditReport, ext: str) -> str:
        """Gera o nome do arquivo com timestamp compacto."""
        ts = audit.audit_timestamp.strftime(_TIMESTAMP_FMT)
        return f"{ts}.{ext}"

    def _save_json(self, audit: AuditReport) -> Path:
        """Serializa e salva o relatório como JSON."""
        device_dir = self._build_device_dir(audit)
        filename = self._build_filename(audit, "json")
        filepath = device_dir / filename

        data = audit.model_dump(mode="json")
        # Garantir datetime como string ISO
        for key in ("audit_timestamp", "baseline_collected_at", "current_collected_at"):
            val = data.get(key)
            if isinstance(val, datetime):
                data[key] = val.isoformat()

        filepath.write_text(
            json.dumps(data, indent=2, ensure_ascii=False, default=str),
            encoding="utf-8",
        )
        return filepath

    def _save_html(self, audit: AuditReport) -> Path:
        """Renderiza e salva o relatório como HTML."""
        device_dir = self._build_device_dir(audit)
        filename = self._build_filename(audit, "html")
        filepath = device_dir / filename

        html_content = self._render_html(audit)
        filepath.write_text(html_content, encoding="utf-8")
        return filepath

    def _render_html(self, audit: AuditReport) -> str:
        """
        Renderiza o relatório como HTML.

        Tenta usar Jinja2 se disponível; caso contrário, usa template
        string nativo do Python.
        """
        try:
            from jinja2 import Environment, FileSystemLoader

            templates_dir = Path(__file__).parent.parent / "templates"
            template_file = templates_dir / "audit_report.html"

            if template_file.exists():
                env = Environment(
                    loader=FileSystemLoader(str(templates_dir)),
                    autoescape=True,
                )
                template = env.get_template("audit_report.html")
                return template.render(
                    audit=audit,
                    severity=audit.severity,
                    Severity=Severity,
                    drift=audit.drift_data,
                    json_dumps=lambda obj: json.dumps(
                        obj, indent=2, ensure_ascii=False, default=str,
                    ),
                )
        except ImportError:
            logger.warning(
                "Jinja2 não disponível — usando template HTML simplificado."
            )

        # Fallback: template string nativo
        return self._render_html_fallback(audit)

    def _render_html_fallback(self, audit: AuditReport) -> str:
        """Template HTML simplificado (sem Jinja2)."""
        severity_colors = {
            Severity.COMPLIANT: "#22c55e",
            Severity.LOW: "#3b82f6",
            Severity.MEDIUM: "#eab308",
            Severity.HIGH: "#f97316",
            Severity.CRITICAL: "#ef4444",
        }
        color = severity_colors.get(audit.severity, "#6b7280")
        drift_json = json.dumps(
            audit.drift_data, indent=2, ensure_ascii=False, default=str,
        )

        return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Auditoria — {audit.hostname} — {audit.audit_timestamp:%Y-%m-%d %H:%M}</title>
    <style>
        body {{ font-family: 'Segoe UI', system-ui, sans-serif; margin: 2rem; background: #f8fafc; color: #1e293b; }}
        .header {{ background: #0f172a; color: #f1f5f9; padding: 1.5rem 2rem; border-radius: 8px; margin-bottom: 2rem; }}
        .header h1 {{ margin: 0 0 0.5rem 0; font-size: 1.5rem; }}
        .severity {{ display: inline-block; padding: 0.25rem 0.75rem; border-radius: 4px; font-weight: 700; color: #fff; background: {color}; }}
        .meta {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 1rem; margin-bottom: 2rem; }}
        .meta-card {{ background: #fff; padding: 1rem; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }}
        .meta-card label {{ font-size: 0.75rem; text-transform: uppercase; color: #64748b; letter-spacing: 0.05em; }}
        .meta-card .value {{ font-size: 1.125rem; font-weight: 600; margin-top: 0.25rem; }}
        .section {{ background: #fff; padding: 1.5rem; border-radius: 8px; margin-bottom: 1.5rem; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }}
        .section h2 {{ margin-top: 0; color: #0f172a; border-bottom: 2px solid #e2e8f0; padding-bottom: 0.5rem; }}
        pre {{ background: #1e293b; color: #e2e8f0; padding: 1rem; border-radius: 6px; overflow-x: auto; font-size: 0.875rem; }}
        .footer {{ text-align: center; color: #94a3b8; font-size: 0.75rem; margin-top: 3rem; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>SentinelNet_FLS — Relatório de Auditoria</h1>
        <span class="severity">{audit.severity.emoji} {audit.severity_label}</span>
    </div>

    <div class="meta">
        <div class="meta-card">
            <label>Cliente</label>
            <div class="value">{audit.customer_id}</div>
        </div>
        <div class="meta-card">
            <label>Dispositivo</label>
            <div class="value">{audit.device_id}</div>
        </div>
        <div class="meta-card">
            <label>Hostname</label>
            <div class="value">{audit.hostname}</div>
        </div>
        <div class="meta-card">
            <label>Auditoria</label>
            <div class="value">{audit.audit_timestamp:%Y-%m-%d %H:%M:%S UTC}</div>
        </div>
    </div>

    <div class="section">
        <h2>Resumo</h2>
        <p>{audit.drift_summary}</p>
        <p><strong>Audit ID:</strong> {audit.audit_id}</p>
    </div>

    <div class="section">
        <h2>Dados de Drift (JSON)</h2>
        <pre>{drift_json}</pre>
    </div>

    <div class="footer">
        <p>Gerado por SentinelNet_FLS &mdash; {audit.audit_timestamp:%Y-%m-%d %H:%M:%S UTC}</p>
    </div>
</body>
</html>"""

    def _save_to_db(self, audit: AuditReport) -> None:
        """Insere o relatório na tabela ``audit_reports`` do SQLite."""
        drift_json = json.dumps(
            audit.drift_data, ensure_ascii=False, default=str,
        )

        with sqlite3.connect(str(self._db_path)) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO audit_reports (
                    audit_id, customer_id, device_id, hostname,
                    severity, severity_label, audit_timestamp,
                    drift_summary, drift_data_json,
                    baseline_collected, current_collected
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    audit.audit_id,
                    audit.customer_id,
                    audit.device_id,
                    audit.hostname,
                    int(audit.severity),
                    audit.severity_label,
                    audit.audit_timestamp.isoformat(),
                    audit.drift_summary,
                    drift_json,
                    audit.baseline_collected_at.isoformat()
                    if audit.baseline_collected_at else None,
                    audit.current_collected_at.isoformat()
                    if audit.current_collected_at else None,
                ),
            )
            conn.commit()
