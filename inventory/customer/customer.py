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

    def collect_inventory(self) -> dict:
        """
        Método a ser implementado por cada driver concreto para coletar
        as informações de inventário dos dispositivos de rede.

        Returns:
            Um dicionário contendo as informações coletadas do inventário.
        """
        raise NotImplementedError("Este método deve ser implementado por subclasses.")
