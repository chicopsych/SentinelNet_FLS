"""
core/
Núcleo do SentinelNet_FLS.

Contém:
- schemas.py      : Modelos Pydantic que definem o contrato de dados de rede.
- base_driver.py  : Classe abstrata que define o contrato de comportamento dos drivers.
- diff_engine.py  : Mecanismo de comparação baseline × estado real (Task 05).
"""

from .diff_engine import DiffEngine, DiffReport
from .schemas import DeviceConfig, FirewallRule, Interface, InterfaceType, Route

__all__ = [
    "DeviceConfig",
    "DiffEngine",
    "DiffReport",
    "FirewallRule",
    "Interface",
    "InterfaceType",
    "Route",
]
