"""
core/base_driver.py
────────────────────
Define o contrato abstrato que todos os drivers de fabricante devem seguir.

Design Decisions
────────────────
1. ABC (Abstract Base Class):
   Usar `abc.ABC` + `@abstractmethod` impede que alguém instancie diretamente
   `NetworkDeviceDriver`, forçando a implementação dos 3 métodos obrigatórios:
   `connect`, `get_config_snapshot` e `disconnect`. Qualquer tentativa de
   instanciar a classe base lança `TypeError` em runtime.

2. Context Manager na classe BASE (não nos drivers filhos):
   O ciclo de vida de uma conexão (abrir → usar → fechar) é idêntico para todos
   os fabricantes: `connect()` ao entrar, `disconnect()` ao sair. Por isso,
   `__enter__` e `__exit__` são implementados aqui com lógica concreta.
   Os drivers filhos herdam esse comportamento automaticamente, sem duplicação.

   Uso idiomático:
       with MikroTikDriver(host="192.168.1.1", username="admin", password="...") as driver:
           snapshot = driver.get_config_snapshot()
   # `disconnect()` é garantido mesmo em caso de exceção.

3. Logging estruturado na base:
   Um logger nomeado com o módulo do driver concreto (`self.__class__.__module__`)
   é criado automaticamente. Isso permite que cada driver tenha seus logs
   rastreáveis par filtrar por fabricante, sem nenhum código adicional no filho.

4. `connected: bool` como flag de estado:
   Evita chamadas duplas a `disconnect()` ou tentativas de coleta sem conexão.
   Os drivers filhos devem setar `self.connected = True` após conectar com sucesso
   e `self.connected = False` ao desconectar.
"""

import logging
from abc import ABC, abstractmethod
from types import TracebackType
from typing import Optional, Type

from core.schemas import DeviceConfig


class NetworkDeviceDriver(ABC):
    """
    Contrato abstrato para drivers de equipamentos de rede.

    Subclasses devem implementar:
        - connect()              → establece sessão SSH/API com o dispositivo
        - get_config_snapshot()  → coleta, parseia e retorna um DeviceConfig
        - disconnect()           → encerra a sessão de forma limpa

    O suporte a context manager (`with` statement) está implementado nesta
    classe base e chama `connect()` / `disconnect()` automaticamente.
    """

    def __init__(
        self,
        host: str,
        username: str,
        password: str,
        port: int = 22,
        timeout: int = 30,
    ) -> None:
        """
        Inicializa os parâmetros de conexão comuns a todos os fabricantes.

        Args:
            host:     Endereço IP ou hostname do dispositivo alvo.
            username: Nome de usuário para autenticação SSH.
            password: Senha de autenticação. Nunca armazenar em texto claro
                      em produção — injetar via variável de ambiente ou cofre.
            port:     Porta SSH. Padrão: 22.
            timeout:  Timeout de conexão em segundos. Padrão: 30.
        """
        self.host: str = host
        self.username: str = username
        self.password: str = password
        self.port: int = port
        self.timeout: int = timeout
        self.connected: bool = False

        # Logger nomeado com a classe concreta, ex: "drivers.mikrotik_driver"
        # Permite filtrar logs por fabricante em ambientes multi-vendor.
        self._logger: logging.Logger = logging.getLogger(
            self.__class__.__module__ + "." + self.__class__.__name__
        )

    # ─── Métodos Abstratos (contrato obrigatório) ─────────────────────────────

    @abstractmethod
    def connect(self) -> None:
        """
        Estabelece a sessão de comunicação com o dispositivo.

        Responsabilidades do driver filho:
            - Instanciar a conexão SSH via Netmiko (ou outra biblioteca).
            - Tratar erros de autenticação, timeout e host inalcançável.
            - Setar `self.connected = True` após sucesso.

        Raises:
            ConnectionError: Se a conexão não puder ser estabelecida.
        """

    @abstractmethod
    def get_config_snapshot(self) -> DeviceConfig:
        """
        Coleta a configuração running do dispositivo e retorna um DeviceConfig.

        Responsabilidades do driver filho:
            - Enviar os comandos necessários para capturar a config (ex: /export).
            - Parsear a saída bruta usando templates TTP/TextFSM.
            - Montar e retornar um objeto DeviceConfig validado pelo Pydantic.

        Returns:
            DeviceConfig: Snapshot completo e validado da configuração atual.

        Raises:
            RuntimeError: Se chamado sem conexão ativa (self.connected == False).
        """

    @abstractmethod
    def disconnect(self) -> None:
        """
        Encerra a sessão de comunicação com o dispositivo.

        Responsabilidades do driver filho:
            - Fechar a sessão SSH de forma limpa.
            - Setar `self.connected = False`.
            - Ser idempotente: chamar disconnect() múltiplas vezes não deve
              lançar exceção.
        """

    # ─── Context Manager (implementado na base — válido para todos os drivers) ─

    def __enter__(self) -> "NetworkDeviceDriver":
        """
        Inicia a sessão ao entrar no bloco `with`.

        Chama `connect()` e retorna a instância do driver para uso no bloco.

        Example:
            with MikroTikDriver(...) as driver:
                snapshot = driver.get_config_snapshot()
        """
        self._logger.info("Conectando a %s:%d ...", self.host, self.port)
        self.connect()
        return self

    def __exit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[TracebackType],
    ) -> bool:
        """
        Garante o encerramento da sessão ao sair do bloco `with`.

        Chama `disconnect()` mesmo se uma exceção foi lançada dentro do bloco,
        evitando sessões SSH orphaned que consumiriam recursos no dispositivo.

        Returns:
            False — não suprime exceções; elas continuam propagando normalmente.
        """
        self._logger.info("Desconectando de %s ...", self.host)
        try:
            self.disconnect()
        except Exception as exc:  # noqa: BLE001
            # Loga o erro de desconexão sem mascarar a exceção original
            self._logger.warning(
                "Falha ao desconectar de %s: %s", self.host, exc
            )
        return False  # Não suprime exceções do bloco `with`

    # ─── Helper de Estado ─────────────────────────────────────────────────────

    def _assert_connected(self) -> None:
        """
        Lança RuntimeError se não há conexão ativa.

        Deve ser chamado no início de `get_config_snapshot()` pelos drivers
        filhos para evitar operações em estado inválido.

        Raises:
            RuntimeError: Se `self.connected` for False.
        """
        if not self.connected:
            raise RuntimeError(
                f"Nenhuma conexão ativa com {self.host}. "
                "Chame connect() antes de get_config_snapshot()."
            )

    def __repr__(self) -> str:
        status = "conectado" if self.connected else "desconectado"
        return (
            f"<{self.__class__.__name__} "
            f"host={self.host!r} port={self.port} [{status}]>"
        )
