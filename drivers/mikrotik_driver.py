"""
drivers/mikrotik_driver.py
───────────────────────────
Driver concreto para dispositivos MikroTik RouterOS.

Funcionamento:
    1. Abre sessão SSH via Netmiko (device_type="mikrotik_routeros").
    2. Dispara `/export verbose` (ou comando configurado) e captura a saída bruta.
    3. Extrai metadados do cabeçalho (hostname, os_version, model) via regex.
    4. Parseia a seção '/ip firewall filter' com TTP → list[FirewallRule].
    5. Parseia a seção '/ip route' com TTP → list[Route].
    6. Monta e retorna DeviceConfig.

Design Decisions:
    - command configurável no __init__ para testes offline com fixture RSC.
    - _parse_header() é puro / sem I/O — testável offline.
    - _parse_ttp_section() é generic: recebe template_name e tipo de retorno.
    - NetmikoTimeoutException / NetmikoAuthenticationException são relançadas
      como ConnectionError para isolar o caller dos detalhes do Netmiko.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from netmiko import ConnectHandler
from netmiko.exceptions import (
    NetmikoAuthenticationException,
    NetmikoTimeoutException,
)
from ttp import ttp

from core.base_driver import NetworkDeviceDriver
from core.schemas import ARPEntry, DeviceConfig, FirewallRule, LLDPNeighbor, MACEntry, Route
from templates import TEMPLATES_DIR


# ──────────────────────────────────────────────────────────────────────────────
# Regex patterns para o cabeçalho do /export verbose
# ──────────────────────────────────────────────────────────────────────────────
_RE_ROUTEROS_VERSION = re.compile(
    r"by\s+RouterOS\s+([\d.]+)", re.IGNORECASE
)
_RE_MODEL = re.compile(
    r"#\s*model\s*=\s*(\S+)", re.IGNORECASE
)
_RE_IDENTITY = re.compile(
    r"/system identity\s*\nset name=(\"[^\"]+\"|[^\s#]+)",
    re.MULTILINE,
)
# Extrai o bloco de texto de uma seção /ip ... até a próxima seção ou fim do arquivo
_RE_SECTION = re.compile(
    r"^(/ip [^\n]+)\n(.*?)(?=^/|\Z)",
    re.MULTILINE | re.DOTALL,
)


class MikroTikDriver(NetworkDeviceDriver):
    """
    Driver de auditoria para MikroTik RouterOS.

    Parameters
    ----------
    host : str
        Endereço IP ou hostname do dispositivo.
    username : str
        Usuário SSH.
    password : str
        Senha SSH.
    port : int
        Porta SSH (padrão: 22).
    timeout : int
        Timeout de conexão em segundos (padrão: 30).
    command : str
        Comando a ser enviado ao dispositivo (padrão: "/export verbose").
        Útil para testes offline: passar a saída de um fixture diretamente.
    """

    #: device_type Netmiko para RouterOS
    DEVICE_TYPE: str = "mikrotik_routeros"

    def __init__(
        self,
        host: str,
        username: str,
        password: str,
        port: int = 22,
        timeout: int = 30,
        command: str = "/export verbose",
    ) -> None:
        super().__init__(host, username, password, port, timeout)
        self.command = command
        self._net_connect: ConnectHandler | None = None

    # ──────────────────────────────────────────────────────────────────────
    # Métodos abstratos obrigatórios
    # ──────────────────────────────────────────────────────────────────────

    @classmethod
    def from_vault(
        cls,
        customer_id: str,
        device_id: str,
        **kwargs: object,
    ) -> "MikroTikDriver":
        """
        Factory method: instancia o driver com credenciais do cofre criptografado.

        Uso::

            driver = MikroTikDriver.from_vault("cliente_a", "borda-01")
            with driver:
                snapshot = driver.get_config_snapshot()

        Args:
            customer_id: Identificador do cliente no cofre.
            device_id:   Identificador do dispositivo no cofre.
            **kwargs:    Parâmetros extras repassados ao ``__init__``
                         (ex: ``command``, ``timeout``).

        Returns:
            Instância de MikroTikDriver configurada.

        Raises:
            utils.vault.VaultError: Se houver problema com o cofre ou credenciais.
        """
        from utils.vault import VaultManager

        vault = VaultManager()
        creds = vault.get_credentials(customer_id, device_id)

        return cls(
            host=creds["host"],
            username=creds["username"],
            password=creds["password"],
            port=creds.get("port", 22),
            **kwargs,  # type: ignore[arg-type]
        )

    def connect(self) -> None:
        """
        Abre a sessão SSH com o dispositivo MikroTik via Netmiko.
        Seta self.connected = True em caso de sucesso.

        Segurança de logs:
            Em caso de falha de autenticação, o erro logado contém apenas
            host, porta e username — NUNCA a senha. Isso previne Data Leakage
            via RotatingFileHandler.

        Raises
        ------
        ConnectionError
            Se o dispositivo não responder (timeout) ou recusar as credenciais.
        """
        self._logger.debug(
            "Iniciando conexão Netmiko com %s:%d (device_type=%s)",
            self.host, self.port, self.DEVICE_TYPE,
        )
        try:
            self._net_connect = ConnectHandler(
                device_type=self.DEVICE_TYPE,
                host=self.host,
                username=self.username,
                password=self.password,
                port=self.port,
                timeout=self.timeout,
                # RouterOS não usa enable — desabilitamos para evitar prompts extras
                secret="",
            )
            self.connected = True
            self._logger.info(
                "Sessão SSH estabelecida com %s (MikroTik RouterOS).", self.host
            )
        except NetmikoTimeoutException as exc:
            self._logger.error("Timeout ao conectar em %s:%d", self.host, self.port)
            raise ConnectionError(
                f"Timeout ao tentar conectar em {self.host}:{self.port}."
            ) from exc
        except NetmikoAuthenticationException as exc:
            # SEGURANÇA: loga apenas host e username — NUNCA a senha.
            # A mensagem original do Netmiko pode conter credenciais.
            self._logger.error(
                "Falha de autenticação em %s para o usuário '%s'. "
                "Verifique as credenciais no cofre.",
                self.host, self.username,
            )
            raise ConnectionError(
                f"Credenciais inválidas para {self.username}@{self.host}."
            ) from exc
        except Exception as exc:
            # SEGURANÇA: captura genérica para evitar que exceções não
            # previstas vazem credenciais no traceback logado.
            self._logger.error(
                "Erro inesperado ao conectar em %s:%d — %s: %s",
                self.host, self.port, type(exc).__name__,
                _sanitize_error(str(exc), self.password),
            )
            raise ConnectionError(
                f"Erro ao conectar em {self.host}:{self.port}."
            ) from exc

    def disconnect(self) -> None:
        """
        Encerra a sessão SSH. Idempotente — seguro chamar mesmo sem conexão ativa.
        Seta self.connected = False.
        """
        if self._net_connect is not None:
            try:
                self._net_connect.disconnect()
                self._logger.info("Sessão SSH com %s encerrada.", self.host)
            except Exception as exc:  # noqa: BLE001
                self._logger.warning(
                    "Erro ao desconectar de %s: %s", self.host, exc
                )
            finally:
                self._net_connect = None
        self.connected = False

    def get_config_snapshot(self) -> DeviceConfig:
        """
        Coleta e parseia a configuração atual do dispositivo.

        Fluxo:
            1. Garante sessão ativa (_assert_connected).
            2. Envia `self.command` e captura saída bruta.
            3. Parseia cabeçalho → hostname, os_version, model.
            4. Parseia firewall filter → list[FirewallRule].
            5. Parseia ip route → list[Route].
            6. Retorna DeviceConfig montado.

        Returns
        -------
        DeviceConfig
            Snapshot estruturado da configuração do dispositivo.
        """
        self._assert_connected()

        self._logger.info(
            "Enviando '%s' para %s ...", self.command, self.host
        )
        raw_output: str = self._net_connect.send_command(  # type: ignore[union-attr]
            self.command,
            read_timeout=120,
            expect_string=r"\[.+\]",   # aguarda prompt RouterOS
        )
        self._logger.debug(
            "Saída bruta recebida de %s (%d caracteres).",
            self.host, len(raw_output),
        )

        header = self._parse_header(raw_output)
        firewall_rules = self._parse_firewall(raw_output)
        routes = self._parse_routes(raw_output)

        config = DeviceConfig(
            hostname=header.get("hostname", self.host),
            vendor="mikrotik",
            model=header.get("model"),
            os_version=header.get("os_version"),
            firewall_rules=firewall_rules,
            routes=routes,
        )

        self._logger.info(
            "Snapshot coletado de %s: %d regras de firewall, %d rotas.",
            self.host, len(firewall_rules), len(routes),
        )
        return config

    # ──────────────────────────────────────────────────────────────────────
    # Métodos de parsing privados
    # ──────────────────────────────────────────────────────────────────────

    def _parse_header(self, raw: str) -> dict[str, str | None]:
        """
        Extrai metadados do cabeçalho ASCII do `/export verbose`.

        O cabeçalho típico do RouterOS tem o formato:
            # jan/01/2024 00:00:00 by RouterOS 7.14.3
            # software id = XXXX-XXXX
            # model = CCR1036-8G-2S+
            # serial number = XXXXXXXXXXXX
            ...
            /system identity
            set name=MeuRouter

        Parameters
        ----------
        raw : str
            Saída bruta do `/export verbose`.

        Returns
        -------
        dict
            Chaves: "hostname", "os_version", "model".
            Valores ausentes são None.
        """
        result: dict[str, str | None] = {
            "hostname": None,
            "os_version": None,
            "model": None,
        }

        # RouterOS version
        m = _RE_ROUTEROS_VERSION.search(raw)
        if m:
            result["os_version"] = m.group(1)
            self._logger.debug("RouterOS version detectada: %s", result["os_version"])

        # Model
        m = _RE_MODEL.search(raw)
        if m:
            result["model"] = m.group(1)
            self._logger.debug("Modelo detectado: %s", result["model"])

        # Hostname via /system identity
        m = _RE_IDENTITY.search(raw)
        if m:
            result["hostname"] = m.group(1).strip('"')
            self._logger.debug("Hostname detectado: %s", result["hostname"])
        else:
            # Fallback: usa o IP do host
            result["hostname"] = self.host
            self._logger.debug(
                "Hostname não encontrado no export; usando IP: %s", self.host
            )

        return result

    def _extract_section(self, raw: str, section_header: str) -> str:
        """
        Extrai o bloco de texto correspondente a uma seção `section_header` do export.

        O RouterOS organiza o /export em seções iniciadas com `/ip ...`, `/system ...`,
        etc. Esta função localiza a seção desejada e retorna apenas as linhas dela,
        sem o cabeçalho (a linha `/ip ...` em si).

        Parameters
        ----------
        raw : str
            Saída bruta do `/export verbose`.
        section_header : str
            Cabeçalho da seção a extrair (ex: "/ip firewall filter").

        Returns
        -------
        str
            Texto das linhas da seção (sem o cabeçalho). String vazia se não encontrada.
        """
        for match in _RE_SECTION.finditer(raw):
            header_found = match.group(1).strip()
            body = match.group(2)
            if header_found == section_header:
                self._logger.debug(
                    "Seção '%s' encontrada (%d chars).", section_header, len(body)
                )
                return body
        self._logger.debug("Seção '%s' não encontrada no export.", section_header)
        return ""

    def _parse_ttp(
        self,
        raw: str,
        template_name: str,
        group_name: str,
    ) -> list[dict[str, Any]]:
        """
        Executa o TTP sobre `raw` usando o template `template_name`.

        Parameters
        ----------
        raw : str
            Saída bruta do dispositivo.
        template_name : str
            Nome do arquivo .ttp dentro de `templates/` (ex: "mikrotik_firewall.ttp").
        group_name : str
            Nome do grupo TTP que contém a lista de itens parseados.

        Returns
        -------
        list[dict]
            Lista de dicts prontos para instanciar os modelos Pydantic.
            Retorna [] se o grupo não for encontrado ou o template não parsear nada.
        """
        template_path = TEMPLATES_DIR / template_name
        if not template_path.exists():
            self._logger.error("Template TTP não encontrado: %s", template_path)
            return []

        template_text = template_path.read_text(encoding="utf-8")
        parser = ttp(data=raw, template=template_text)
        parser.parse()
        results = parser.result(structure="flat_list")

        # results é list[dict] ou list[list[dict]] dependendo do TTP version
        # Normalizamos para list[dict] pegando o group_name
        items: list[dict[str, Any]] = []
        for block in results:
            if isinstance(block, dict):
                data = block.get(group_name, [])
            elif isinstance(block, list):
                # flat_list pode vir como [[{...}]]
                inner = block[0] if block else {}
                data = inner.get(group_name, []) if isinstance(inner, dict) else []
            else:
                continue

            if isinstance(data, dict):
                # TTP retorna dict quando há apenas 1 match
                items.append(data)
            elif isinstance(data, list):
                items.extend(data)

        self._logger.debug(
            "TTP '%s': %d itens encontrados no grupo '%s'.",
            template_name, len(items), group_name,
        )
        return items

    def _parse_firewall(self, raw: str) -> list[FirewallRule]:
        """
        Parseia a seção `/ip firewall filter` e retorna list[FirewallRule].
        Itens inválidos (campos obrigatórios ausentes) são descartados com warning.
        """
        section = self._extract_section(raw, "/ip firewall filter")
        if not section.strip():
            self._logger.debug("Seção /ip firewall filter vazia ou ausente.")
            return []
        raw_items = self._parse_ttp(section, "mikrotik_firewall.ttp", "firewall_rules")
        rules: list[FirewallRule] = []
        for item in raw_items:
            try:
                rules.append(FirewallRule(**item))
            except Exception as exc:  # noqa: BLE001
                self._logger.warning(
                    "Descartando regra de firewall inválida %s: %s", item, exc
                )
        return rules

    def _parse_routes(self, raw: str) -> list[Route]:
        """
        Parseia a seção `/ip route` e retorna list[Route].
        Itens inválidos são descartados com warning.
        """
        section = self._extract_section(raw, "/ip route")
        if not section.strip():
            self._logger.debug("Seção /ip route vazia ou ausente.")
            return []
        raw_items = self._parse_ttp(section, "mikrotik_routes.ttp", "routes")
        routes: list[Route] = []
        for item in raw_items:
            try:
                routes.append(Route(**item))
            except Exception as exc:  # noqa: BLE001
                self._logger.warning(
                    "Descartando rota inválida %s: %s", item, exc
                )
        return routes

    # ──────────────────────────────────────────────────────────────────────
    # Métodos de Topologia (L2/L3)
    # ──────────────────────────────────────────────────────────────────────

    def get_arp_table(self) -> list[ARPEntry]:
        """
        Coleta a tabela ARP do MikroTik via ``/ip arp print terse``.

        Returns:
            Lista de ARPEntry com ip_address, mac_address, interface.
        """
        self._assert_connected()

        self._logger.info("Coletando tabela ARP de %s ...", self.host)
        raw = self._net_connect.send_command(  # type: ignore[union-attr]
            "/ip arp print terse",
            read_timeout=30,
            expect_string=r"\[.+\]",
        )

        raw_items = self._parse_ttp(raw, "mikrotik_arp.ttp", "arp_entries")
        entries: list[ARPEntry] = []
        for item in raw_items:
            try:
                entries.append(ARPEntry(**item))
            except Exception as exc:  # noqa: BLE001
                self._logger.warning(
                    "Descartando entrada ARP inválida %s: %s", item, exc
                )

        self._logger.info(
            "Tabela ARP de %s: %d entradas coletadas.", self.host, len(entries)
        )
        return entries

    def get_mac_table(self) -> list[MACEntry]:
        """
        Coleta a tabela MAC/bridge host via ``/interface bridge host print terse``.

        Returns:
            Lista de MACEntry com mac_address, interface, is_local.
        """
        self._assert_connected()

        self._logger.info("Coletando tabela MAC/bridge de %s ...", self.host)
        raw = self._net_connect.send_command(  # type: ignore[union-attr]
            "/interface bridge host print terse",
            read_timeout=30,
            expect_string=r"\[.+\]",
        )

        raw_items = self._parse_ttp(raw, "mikrotik_bridge_host.ttp", "bridge_hosts")
        entries: list[MACEntry] = []
        for item in raw_items:
            try:
                # MikroTik bridge host: on-interface é a porta física
                item.setdefault("switch_port", item.get("interface"))
                entries.append(MACEntry(**item))
            except Exception as exc:  # noqa: BLE001
                self._logger.warning(
                    "Descartando entrada MAC inválida %s: %s", item, exc
                )

        self._logger.info(
            "Tabela MAC de %s: %d entradas coletadas.", self.host, len(entries)
        )
        return entries

    def get_lldp_neighbors(self) -> list[LLDPNeighbor]:
        """
        Coleta vizinhos via ``/ip neighbor print detail``.

        MikroTik usa seu próprio MNDP mas também reporta vizinhos
        LLDP e CDP. O output é parseado com TTP.

        Returns:
            Lista de LLDPNeighbor.
        """
        self._assert_connected()

        self._logger.info("Coletando vizinhos LLDP/MNDP de %s ...", self.host)
        raw = self._net_connect.send_command(  # type: ignore[union-attr]
            "/ip neighbor print detail",
            read_timeout=30,
            expect_string=r"\[.+\]",
        )

        raw_items = self._parse_ttp(raw, "mikrotik_neighbors.ttp", "neighbors")
        neighbors: list[LLDPNeighbor] = []
        for item in raw_items:
            try:
                neighbors.append(LLDPNeighbor(**item))
            except Exception as exc:  # noqa: BLE001
                self._logger.warning(
                    "Descartando vizinho inválido %s: %s", item, exc
                )

        self._logger.info(
            "Vizinhos de %s: %d descobertos.", self.host, len(neighbors)
        )
        return neighbors


# ─── Helpers de Segurança ─────────────────────────────────────────────────────

def _sanitize_error(message: str, password: str) -> str:
    """
    Remove a senha de uma mensagem de erro para evitar Data Leakage nos logs.

    Se a senha aparecer no traceback/mensagem de exceção (ex: Netmiko pode
    incluí-la em erros de conexão), ela é substituída por ``'***'``.

    Args:
        message:  Texto do erro original.
        password: Senha que deve ser mascarada.

    Returns:
        Mensagem sanitizada, sem credenciais expostas.
    """
    if password and password in message:
        return message.replace(password, "***")
    return message
