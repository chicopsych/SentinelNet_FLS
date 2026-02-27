"""
core/services/
Camada de serviços do SentinelNet_FLS.

Contém lógica de negócio agnóstica à interface:
- discovery   : Varredura nmap de ativos na rede.
- reachability : Testes de conectividade (ping + SNMP).
- overview     : KPIs consolidados do ambiente.
- device       : Correlação dispositivo ↔ incidente.
- audit        : Orquestração DiffEngine + IncidentEngine.
- remediation  : Fluxo de remediação controlada.
"""
