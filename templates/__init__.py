"""
templates/
──────────
Diretório de templates TTP usados pelos drivers para parsear
saídas de dispositivos em modelos Pydantic estruturados.

Templates disponíveis:
    mikrotik_firewall.ttp  — /ip firewall filter  → list[FirewallRule]
    mikrotik_routes.ttp    — /ip route            → list[Route]

Uso:
    from templates import TEMPLATES_DIR
    template_path = TEMPLATES_DIR / "mikrotik_firewall.ttp"
"""

from pathlib import Path

TEMPLATES_DIR: Path = Path(__file__).parent

__all__ = ["TEMPLATES_DIR"]
