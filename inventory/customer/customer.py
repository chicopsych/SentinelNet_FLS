# Script responsável por definir a classe base para drivers de clientes,
# que se conectam a dispositivos de rede para coletar informações de inventário.
# Informações que o inventário deve conter:
# - Hostname/IP
# - Tipo de dispositivo (ex: switch, router, AP)
# - Fabricante (ex: MikroTik, Cisco)
# - Credenciais de acesso (username/password ou chave SSH)
# - Porta de acesso (ex: 22 para SSH)
# - Layer de rede (ex: acesso, distribuição, core)
# - Configurações específicas do fabricante (ex: comandos de coleta, endpoints API)
# - Outras informações relevantes (ex: localização física, modelo, etc.)
#
"""
customer.py
Definição da classe base para drivers de clientes.
"""

from internalloggin.logger import setup_logger


# ── Inventário de dispositivos ────────────────────────────────────────────────
# Cada entrada define o customer_id, device_id e vendor do dispositivo.
# O host e as credenciais residem EXCLUSIVAMENTE no VaultManager (inventory/vault.enc)
# e nunca devem ser inseridos aqui.

DEVICE_INVENTORY: list[dict] = [
    {
        "customer_id": "cliente_a",
        "device_id":   "borda-01",
        "vendor":      "mikrotik",
    },
]


class Customer:
    """
    Classe base para drivers de clientes.

    Cada driver concreto (ex: MikroTikCustomer) deve herdar desta classe
    e implementar os métodos necessários para coletar informações de inventário
    dos dispositivos de rede do cliente.
    """

    def __init__(self, inventory_data: dict):
        """
        Inicializa o driver com os dados do inventário.

        Args:
            inventory_data: Dicionário contendo as informações do inventário
                            para os dispositivos do cliente.
        """
        self.inventory_data = inventory_data
        self.logger = setup_logger(self.__class__.__module__ + "." + self.__class__.__name__)
        self.logger.debug("Customer inicializado com inventory_data.")

    def collect_inventory(self) -> dict:
        """
        Método a ser implementado por cada driver concreto para coletar
        as informações de inventário dos dispositivos de rede.

        Returns:
            Um dicionário contendo as informações coletadas do inventário.
        """
        self.logger.error("collect_inventory() não implementado na subclasse.")
        raise NotImplementedError("Este método deve ser implementado por subclasses.")
