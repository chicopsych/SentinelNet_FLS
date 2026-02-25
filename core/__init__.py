"""
core/
Núcleo do SentinelNet_FLS.

Contém:
- schemas.py         : Modelos Pydantic que definem o contrato de dados de rede.
- base_driver.py     : Classe abstrata que define o contrato de comportamento dos drivers.
- diff_engine.py     : Mecanismo de comparação baseline × estado real (Task 05).
- audit_report.py    : Modelo de relatório e classificação de severidade (Task 06).
- report_manager.py  : Persistência JSON / HTML / SQLite de relatórios (Task 06).
"""

from .audit_report import AuditReport, Severity, classify_severity
from .diff_engine import DiffEngine, DiffReport
from .report_manager import ReportManager
from .schemas import DeviceConfig, FirewallRule, Interface, InterfaceType, Route

__all__ = [
    "AuditReport",
    "DeviceConfig",
    "DiffEngine",
    "DiffReport",
    "FirewallRule",
    "Interface",
    "InterfaceType",
    "ReportManager",
    "Route",
    "Severity",
    "classify_severity",
]
