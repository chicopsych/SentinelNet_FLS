"""
main.py
────────
Ponto de entrada do SentinelNet_FLS.

Fluxo esperado (a implementar nas Tasks seguintes):
    1. Carregar inventário (lista de dispositivos e credenciais).
    2. Para cada dispositivo, instanciar o driver correspondente.
    3. Coletar o snapshot de configuração atual via driver.
    4. Carregar a baseline JSON do inventário/.
    5. Comparar snapshot × baseline com o Diff Engine (Task 05).
    6. Persistir relatório de desvios (Task 06). ✅
"""

import json

from core import DiffEngine, ReportManager
from core.audit_report import AuditReport
from core.schemas import DeviceConfig, FirewallRule, Interface, InterfaceType, Route
from internalloggin.logger import setup_logger


logger = setup_logger(__name__)


def demo_diff_engine() -> None:
    """
    Demonstração do Diff Engine (Task 05).

    Cria dois DeviceConfig fabricados — um baseline e um com drift
    simulado — e executa a comparação para validar a detecção de
    adições, remoções e modificações.
    """
    logger.info("── Demo: Diff Engine (Task 05) ──")

    # ── Baseline: estado esperado ─────────────────────────────────────────
    baseline = DeviceConfig(
        hostname="borda-01",
        vendor="mikrotik",
        model="CCR1036-8G-2S+",
        os_version="7.14",
        interfaces=[
            Interface(
                name="ether1",
                interface_type=InterfaceType.ETHER,
                ip_addresses=["192.168.1.1/24"],
                enabled=True,
                comment="Uplink ISP",
            ),
            Interface(
                name="ether2",
                interface_type=InterfaceType.ETHER,
                ip_addresses=["10.0.0.1/30"],
                enabled=True,
                comment="LAN Core",
            ),
        ],
        routes=[
            Route(destination="0.0.0.0/0", gateway="192.168.1.254", interface="ether1"),
            Route(destination="10.10.0.0/16", gateway="10.0.0.2", interface="ether2"),
        ],
        firewall_rules=[
            FirewallRule(chain="input", action="accept", protocol="tcp", dst_port="22", comment="Allow SSH"),
            FirewallRule(chain="input", action="accept", protocol="icmp", comment="Allow Ping"),
            FirewallRule(chain="input", action="drop", comment="Drop All Input"),
        ],
    )

    # ── Current: estado real com drift simulado ───────────────────────────
    # Cenários de Firewall Drift demonstrados:
    #   [0] POSITION DRIFT: "Allow SSH" substituída por "Allow Ping" (troca)
    #   [1] POSITION DRIFT: "Allow Ping" substituída por "Allow SSH" (troca)
    #   [2] PARAMETER DRIFT: "Drop All Input" action mudou para "reject"
    #   [3] EXTRA RULE: regra nova não documentada na baseline
    current = DeviceConfig(
        hostname="borda-01",
        vendor="mikrotik",
        model="CCR1036-8G-2S+",
        os_version="7.15",  # DRIFT: OS atualizado sem aprovação
        interfaces=[
            Interface(
                name="ether1",
                interface_type=InterfaceType.ETHER,
                ip_addresses=["192.168.1.1/24"],
                enabled=True,
                comment="Uplink ISP",
            ),
            # DRIFT: ether2 mudou IP
            Interface(
                name="ether2",
                interface_type=InterfaceType.ETHER,
                ip_addresses=["10.0.0.5/30"],  # era 10.0.0.1/30
                enabled=True,
                comment="LAN Core",
            ),
            # DRIFT: interface adicionada sem aprovação
            Interface(
                name="ether3",
                interface_type=InterfaceType.ETHER,
                ip_addresses=["172.16.0.1/24"],
                enabled=True,
                comment="Rede Convidados",
            ),
        ],
        routes=[
            Route(destination="0.0.0.0/0", gateway="192.168.1.254", interface="ether1"),
            # DRIFT: rota 10.10.0.0/16 removida (baseline tem 2, current tem 1)
        ],
        firewall_rules=[
            # POSITION DRIFT: técnico inverteu posições das regras 0 e 1
            # Risco de SHADOWING: "Allow Ping" agora está antes de "Allow SSH"
            FirewallRule(chain="input", action="accept", protocol="icmp", comment="Allow Ping"),
            FirewallRule(chain="input", action="accept", protocol="tcp", dst_port="22", comment="Allow SSH"),
            # PARAMETER DRIFT: regra mantém comment mas action mudou
            FirewallRule(chain="input", action="reject", comment="Drop All Input"),
            # EXTRA RULE: regra nova não documentada na baseline
            FirewallRule(chain="forward", action="accept", src_address="192.168.88.0/24", comment="Guest Forward"),
        ],
    )

    # ── Executa comparação ────────────────────────────────────────────────
    report = DiffEngine.compare(baseline, current)

    logger.info("Resultado da Auditoria:")
    logger.info(json.dumps(report.to_dict(), indent=2, ensure_ascii=False, default=str))

    if report.has_drift:
        logger.error("AUDITORIA CONCLUÍDA: Desvios detectados! — %s", report.summary())
    else:
        logger.info("AUDITORIA CONCLUÍDA: Equipamento em conformidade.")

    # ── Persiste relatório (Task 06) ──────────────────────────────────────
    audit = AuditReport.from_diff_report(
        report=report,
        customer_id="cliente_a",
        device_id="borda-01",
        hostname=current.hostname,
        baseline_collected_at=baseline.collected_at,
        current_collected_at=current.collected_at,
    )

    manager = ReportManager()
    paths = manager.persist(audit)

    logger.info("Relatórios gerados:")
    for fmt, path in paths.items():
        logger.info("  [%s] %s", fmt.upper(), path)

    # ── Estatísticas do histórico ─────────────────────────────────────────
    stats = manager.get_stats()
    logger.info("Estatísticas globais: %s", stats)


def main() -> None:
    logger.info("SentinelNet_FLS iniciado.")

    # Demonstração do Diff Engine + Relatório — remover/substituir quando
    # o fluxo completo (inventário → driver → diff → relatório) estiver pronto.
    demo_diff_engine()


if __name__ == "__main__":
    main()
