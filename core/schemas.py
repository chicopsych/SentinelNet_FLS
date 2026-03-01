"""
core/schemas.py
───────────────
Define os modelos Pydantic que representam o estado completo de um equipamento
de rede — a "Fonte Única da Verdade" do SentinelNet_FLS.

Design Decisions
────────────────
1. Hierarquia em 4 níveis:
       Interface / Route / FirewallRule  →  DeviceConfig (Aggregate Root)

   Todos os submodelos são sempre acessados ATRAVÉS de DeviceConfig.
   Isso permite serializar/desserializar um snapshot completo com uma única
   chamada (DeviceConfig.model_dump() / DeviceConfig.model_validate()).

2. ConfigDict(str_strip_whitespace=True):
   CLIs frequentemente retornam strings com espaços extras. A normalização
   automática reduz falsos positivos no Diff Engine (Task 05).

3. Campos Optional vs obrigatórios:
   Campos que podem legitimamente estar ausentes no dispositivo real (ex: um
   endereço IP numa interface bridge sem configuração L3) são Optional[str]
   para evitar erros de validação em baselines parcialmente preenchidos.

4. `collected_at` com timezone UTC:
   Timestamps sem timezone são ambíguos em ambientes multi-região. O campo
   usa `datetime` e o default_factory garante preenchimento automático.

5. Modelo Interface alinhado ao MikroTik RouterOS:
   - ip_addresses: list[str] (CIDR) em vez de ip_address + prefix_len separados.
     MikroTik armazena IPs em CIDR na seção /ip address e permite múltiplos
     endereços por interface. A lista facilita diff e round-trip JSON.
   - InterfaceType (Enum): classifica a interface (ether, vlan, bridge, etc.)
     para permitir validações específicas por tipo.
   - mac_address: normalizado para XX:XX:XX:XX:XX:XX via field_validator.
   - enabled vs running: MikroTik distingue estado administrativo (disabled=no)
     do estado operacional (running=yes — link fisicamente ativo).
   - Backward compatibility: o model_validator (mode="before") aceita a forma
     legada ip_address + prefix_len e converte para ip_addresses
     automaticamente.
"""

import re
from datetime import datetime, timezone
from enum import Enum
from ipaddress import AddressValueError, IPv4Interface
from typing import Optional

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)


# ─── Enum: Tipo de Interface ─────────────────────────────────────────────────

class InterfaceType(str, Enum):
    """
    Classifica o tipo de interface conforme nomenclatura MikroTik/RouterOS.

    Usar str como mixin garante que os valores são serializados como strings
    simples no JSON (ex: "vlan"), sem o prefixo "InterfaceType.vlan".
    Isso mantém o JSON limpo e compatível com outras ferramentas.
    """

    ETHER = "ether"          # Interface Ethernet física (ex: ether1)
    WLAN = "wlan"            # Interface wireless (ex: wlan1)
    BRIDGE = "bridge"        # Interface bridge lógica (ex: bridge1)
    VLAN = "vlan"            # Interface VLAN 802.1q (ex: vlan10)
    BONDING = "bonding"      # Interface de bonding/LAG (ex: bond0)
    LOOPBACK = "loopback"    # Interface de loopback (ex: lo)
    TUNNEL = "tunnel"        # Interfaces de túnel (ex: eoip, gre, l2tp)
    OTHER = "other"          # Demais tipos (PPP, SSTP, veth, etc.)


# ─── Modelo 1: Interface de Rede (alinhado ao MikroTik) ──────────────────────

class Interface(BaseModel):
    """
    Representa uma interface de rede lógica ou física, modelada para cobrir
    fielmente a saída do MikroTik RouterOS (/interface print + /ip address print).

    Suporta múltiplos endereços IP por interface (como o RouterOS permite).

    Backward compatibility:
        Ainda aceita o formato legado com ip_address + prefix_len separados.
        O model_validator (mode="before") converte automaticamente para o formato
        canônico ip_addresses: list[str] com notação CIDR.

    Exemplos de instanciação:

        # Formato canônico (CIDR):
        iface = Interface(name="ether1", ip_addresses=["192.168.1.1/24"])

        # Formato legado (ainda aceito):
        iface = Interface(name="ether1", ip_address="192.168.1.1", prefix_len=24)

        # Interface VLAN:
        iface = Interface(
            name="vlan10",
            interface_type=InterfaceType.VLAN,
            vlan_id=10,
            vlan_interface="ether2",
        )
    """

    model_config = ConfigDict(str_strip_whitespace=True)

    # ── Identificação ─────────────────────────────────────────────────────────
    name: str = Field(
        ...,
        description=(
            "Identificador único da interface no dispositivo "
            "(ex: 'ether1', 'bridge1', 'vlan10', 'wlan1')."
        ),
    )
    interface_type: InterfaceType = Field(
        default=InterfaceType.ETHER,
        description="Tipo da interface conforme classificação do RouterOS.",
    )

    # ── Estado ────────────────────────────────────────────────────────────────
    enabled: bool = Field(
        default=True,
        description=(
            "Estado administrativo da interface. "
            "False equivale a 'disabled=yes' no RouterOS. "
            "Controla se o sistema operacional considera a interface ativa."
        ),
    )
    running: Optional[bool] = Field(
        default=None,
        description=(
            "Estado operacional da interface (link físico ativo). "
            "True = 'running' no /interface print. "
            "Distinto de enabled: uma interface pode estar enabled mas não running "
            "(ex: cabo desconectado)."
        ),
    )

    # ── Camada 2 ──────────────────────────────────────────────────────────────
    mac_address: Optional[str] = Field(
        default=None,
        description=(
            "Endereço MAC da interface em formato XX:XX:XX:XX:XX:XX (maiúsculo). "
            "Normalizado automaticamente pelo validador. "
            "Ausente em interfaces lógicas (bridge, vlan, tunnel)."
        ),
    )
    mtu: Optional[int] = Field(
        default=None,
        ge=68,
        le=65535,
        description=(
            "MTU configurado na interface. "
            "Padrão MikroTik: 1500 para Ethernet, 65535 para loopback. "
            "Inteiro entre 68 e 65535 (RFC 791)."
        ),
    )

    # ── Camada 3 ──────────────────────────────────────────────────────────────
    ip_addresses: list[str] = Field(
        default_factory=list,
        description=(
            "Lista de endereços IPv4 em notação CIDR atribuídos à interface "
            "(ex: ['192.168.1.1/24', '10.0.0.1/30']). "
            "No MikroTik, endereços IP ficam na seção /ip address e são "
            "vinculados à interface pelo campo 'interface='. "
            "Cada entrada é validada pelo field_validator como IPv4Interface."
        ),
    )

    # ── VLAN (apenas para interface_type=InterfaceType.VLAN) ──────────────────
    vlan_id: Optional[int] = Field(
        default=None,
        ge=1,
        le=4094,
        description=(
            "ID da VLAN (802.1q). Obrigatório para interfaces do tipo VLAN. "
            "Inteiro entre 1 e 4094 (0 e 4095 são reservados)."
        ),
    )
    vlan_interface: Optional[str] = Field(
        default=None,
        description=(
            "Interface física ou bridge pai desta VLAN "
            "(ex: 'ether2', 'bridge1'). "
            "Equivale ao campo 'interface=' em /interface vlan."
        ),
    )

    # ── Metadados ─────────────────────────────────────────────────────────────
    comment: Optional[str] = Field(
        default=None,
        description=(
            "Comentário descritivo da interface. "
            "Equivale ao campo 'comment=' no MikroTik RouterOS. "
            "Útil para documentar a função da interface (ex: 'Uplink ISP')."
        ),
    )
    slave: Optional[bool] = Field(
        default=None,
        description=(
            "True se a interface é membro (porta escrava) de uma bridge ou bonding. "
            "Equivale ao flag 'S' em /interface print no RouterOS."
        ),
    )

    # ── Validators ────────────────────────────────────────────────────────────

    @model_validator(mode="before")
    @classmethod
    def _compat_legacy_ip_fields(cls, data: object) -> object:
        """
        Backward compatibility: converte o formato legado ip_address + prefix_len
        para o formato canônico ip_addresses: list[str] (CIDR).

        Também aceita ip_address já em formato CIDR (ex: '192.168.1.1/24').

        Casos tratados:
            {"ip_address": "192.168.1.1", "prefix_len": 24}  →  ip_addresses=["192.168.1.1/24"]
            {"ip_address": "192.168.1.1/24"}                 →  ip_addresses=["192.168.1.1/24"]
            {"ip_addresses": ["192.168.1.1/24"]}             →  sem alteração (caminho padrão)
        """
        if not isinstance(data, dict):
            return data

        ip_raw: Optional[str] = data.pop("ip_address", None)
        prefix_raw: Optional[int] = data.pop("prefix_len", None)

        # Ignora se já foi fornecido ip_addresses diretamente
        if ip_raw is not None and "ip_addresses" not in data:
            if "/" in str(ip_raw):
                # Já está em formato CIDR
                data["ip_addresses"] = [ip_raw]
            elif prefix_raw is not None:
                data["ip_addresses"] = [f"{ip_raw}/{prefix_raw}"]
            else:
                # IP sem prefixo: assume /32 (host route)
                data["ip_addresses"] = [f"{ip_raw}/32"]

        return data

    @field_validator("mac_address", mode="before")
    @classmethod
    def _normalize_mac_address(cls, value: Optional[str]) -> Optional[str]:
        """
        Normaliza e valida o endereço MAC.

        Aceita os formatos mais comuns:
            - Dois-pontos separados: 00:0c:29:ab:cd:ef  (Linux/MikroTik padrão)
            - Traço separado:        00-0C-29-AB-CD-EF  (Windows)
            - Sem separador:         000C29ABCDEF

        Retorna sempre no formato canônico XX:XX:XX:XX:XX:XX em maiúsculo.

        Raises:
            ValueError: Se o formato não for reconhecido como um MAC válido.
        """
        if value is None:
            return None

        # Remove separadores e normaliza para 12 hex dígitos
        cleaned = re.sub(r"[:\-\.]", "", value).upper()

        if not re.fullmatch(r"[0-9A-F]{12}", cleaned):
            raise ValueError(
                f"Endereço MAC inválido: '{value}'. "
                "Formato esperado: XX:XX:XX:XX:XX:XX (hexadecimal, 6 grupos de 2 dígitos)."
            )

        # Reconstrói no formato canônico com dois-pontos
        return ":".join(cleaned[i:i + 2] for i in range(0, 12, 2))

    @field_validator("ip_addresses", mode="before")
    @classmethod
    def _validate_ip_addresses(cls, values: object) -> list[str]:
        """
        Valida e normaliza cada endereço IP/CIDR da lista.

        Usa o módulo stdlib `ipaddress.IPv4Interface` para validação rigorosa:
            - '192.168.1.1/24' → válido, retorna '192.168.1.1/24'
            - '192.168.1.300/24' → ValueError (octeto inválido)
            - '192.168.1.1/33'  → ValueError (prefixo inválido)

        Aceita entrada como string única (converte para lista de um elemento)
        para facilitar a integração com parsers TTP que retornam string.

        Raises:
            ValueError: Se qualquer entrada não for um endereço CIDR válido.
        """
        if isinstance(values, str):
            # Parser retornou string única — converte para lista
            values = [values]

        if not isinstance(values, list):
            raise ValueError(
                f"ip_addresses deve ser uma lista de strings CIDR, recebeu: {type(values).__name__}"
            )

        normalized: list[str] = []
        for entry in values:
            entry = str(entry).strip()
            # Adiciona /32 se não houver prefixo (IP host isolado)
            if "/" not in entry:
                entry = f"{entry}/32"
            try:
                iface = IPv4Interface(entry)
            except (AddressValueError, ValueError) as exc:
                raise ValueError(
                    f"Endereço IP/CIDR inválido: '{entry}'. "
                    f"Detalhe: {exc}"
                ) from exc
            # Retorna o endereço do host com o prefixo (preserva o IP do host, não a rede)
            # ex: '192.168.1.1/24' (e não '192.168.1.0/24' que seria a rede)
            normalized.append(f"{iface.ip}/{iface.network.prefixlen}")

        return normalized

    @model_validator(mode="after")
    def _validate_vlan_consistency(self) -> "Interface":
        """
        Regra de negócio: interfaces do tipo VLAN devem ter vlan_id definido.

        Detecta configurações inconsistentes que passariam pelos field_validators
        mas que violam as regras semânticas do RouterOS.

        Raises:
            ValueError: Se uma interface VLAN não tiver vlan_id configurado.
        """
        if self.interface_type == InterfaceType.VLAN and self.vlan_id is None:
            raise ValueError(
                f"Interface '{self.name}' é do tipo VLAN mas não tem 'vlan_id' definido. "
                "O vlan_id é obrigatório para interfaces VLAN (802.1q)."
            )
        return self


# ─── Modelo 2: Rota de Rede ───────────────────────────────────────────────────

class Route(BaseModel):
    """
    Representa uma entrada na tabela de roteamento do dispositivo.

    Exemplos de uso:
    >>> route = Route(destination="0.0.0.0/0", gateway="10.0.0.1", route_type="static")
    >>> route.distance
    1
    """

    model_config = ConfigDict(str_strip_whitespace=True)

    destination: str = Field(
        ...,
        description="Rede de destino em notação CIDR (ex: '0.0.0.0/0', '10.0.0.0/8').",
    )
    gateway: Optional[str] = Field(
        default=None,
        description="Endereço IP do próximo salto (next-hop). None para rotas conectadas.",
    )
    interface: Optional[str] = Field(
        default=None,
        description="Interface de saída associada à rota (ex: 'ether1').",
    )
    distance: int = Field(
        default=1,
        ge=0,
        le=255,
        description="Distância administrativa da rota. Padrão 1 (estática). Inteiro entre 0 e 255.",
    )
    route_type: str = Field(
        default="static",
        description="Origem da rota (ex: 'static', 'ospf', 'bgp', 'connected', 'rip').",
    )


# ─── Modelo 3: Regra de Firewall ──────────────────────────────────────────────

class FirewallRule(BaseModel):
    """
    Representa uma regra de firewall (filter, NAT ou mangle).

    O campo `chain` é mandatório porque define o contexto de aplicação da regra.
    Sem chain, a regra é semanticamente inválida.

    Exemplos de uso:
    >>> rule = FirewallRule(chain="input", action="drop", src_address="10.0.0.5")
    >>> rule.disabled
    False
    """

    model_config = ConfigDict(str_strip_whitespace=True)

    chain: str = Field(
        ...,
        description="Cadeia de aplicação da regra (ex: 'input', 'forward', 'output').",
    )
    action: str = Field(
        ...,
        description="Ação tomada ao casar com a regra (ex: 'accept', 'drop', 'reject', 'masquerade').",
    )
    src_address: Optional[str] = Field(
        default=None,
        description="Endereço/rede de origem em CIDR. None para qualquer origem.",
    )
    dst_address: Optional[str] = Field(
        default=None,
        description="Endereço/rede de destino em CIDR. None para qualquer destino.",
    )
    protocol: Optional[str] = Field(
        default=None,
        description="Protocolo de transporte (ex: 'tcp', 'udp', 'icmp'). None para todos.",
    )
    src_port: Optional[str] = Field(
        default=None,
        description="Porta(s) de origem (ex: '80', '1024-65535'). None para qualquer porta.",
    )
    dst_port: Optional[str] = Field(
        default=None,
        description="Porta(s) de destino (ex: '443', '22'). None para qualquer porta.",
    )
    comment: Optional[str] = Field(
        default=None,
        description="Comentário descritivo da regra. Útil para rastreabilidade.",
    )
    disabled: bool = Field(
        default=False,
        description="True se a regra está desativada no dispositivo.",
    )


# ─── Modelo Raiz: DeviceConfig (Aggregate Root) ───────────────────────────────

class DeviceConfig(BaseModel):
    """
    Snapshot completo da configuração de um equipamento de rede.

    Representa tanto a "Baseline" (estado esperado, armazenado em JSON)
    quanto o "Snapshot" (estado real, coletado via SSH pelo driver).

    O Diff Engine (Task 05) receberá dois objetos DeviceConfig — um de cada
    origem — e calculará as divergências entre eles.

    Serialização:
        # Salvar baseline em arquivo:
        with open("inventory/cliente_a/roteador1.json", "w") as f:
            f.write(device.model_dump_json(indent=2))

        # Carregar baseline de arquivo:
        device = DeviceConfig.model_validate_json(Path("...").read_text())

    Exemplos de uso:
    >>> cfg = DeviceConfig(hostname="roteador1", vendor="mikrotik")
    >>> cfg.interfaces
    []
    """

    model_config = ConfigDict(str_strip_whitespace=True)

    hostname: str = Field(
        ...,
        description="Nome do equipamento (ex: 'roteador1', 'sw-core-sp01').",
    )
    vendor: str = Field(
        ...,
        description="Fabricante do equipamento em caixa baixa (ex: 'mikrotik', 'cisco', 'fiberhome').",
    )
    model: Optional[str] = Field(
        default=None,
        description="Modelo do hardware (ex: 'CCR1036-8G-2S+', 'ISR4321').",
    )
    os_version: Optional[str] = Field(
        default=None,
        description="Versão do firmware/SO no momento da coleta (ex: '7.14', '15.6(3)M').",
    )
    interfaces: list[Interface] = Field(
        default_factory=list,
        description="Lista de interfaces configuradas no dispositivo.",
    )
    routes: list[Route] = Field(
        default_factory=list,
        description="Lista de entradas da tabela de roteamento.",
    )
    firewall_rules: list[FirewallRule] = Field(
        default_factory=list,
        description="Lista de regras de firewall (filter, NAT, mangle).",
    )
    collected_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Timestamp UTC de quando a configuração foi coletada ou definida.",
    )


# ═══════════════════════════════════════════════════════════════════════════════
# Modelos de Topologia (Mapeamento L2 / L3)
# ═══════════════════════════════════════════════════════════════════════════════


class ARPEntry(BaseModel):
    """
    Entrada da tabela ARP — correlação L3 (IP ↔ MAC) obtida de um roteador
    ou switch de camada 3.

    Fonte de dados:
        - MikroTik: ``/ip arp print``
        - SNMP: ipNetToMediaTable (OID 1.3.6.1.2.1.4.22)
    """

    model_config = ConfigDict(str_strip_whitespace=True)

    ip_address: str = Field(
        ..., description="Endereço IPv4 do ativo na rede."
    )
    mac_address: str = Field(
        ..., description="MAC address associado ao IP (formato XX:XX:XX:XX:XX:XX)."
    )
    interface: Optional[str] = Field(
        default=None,
        description="Interface do roteador/switch onde a entrada ARP foi aprendida.",
    )
    vlan_id: Optional[int] = Field(
        default=None, ge=1, le=4094,
        description="VLAN ID da interface (se disponível).",
    )
    last_seen: Optional[datetime] = Field(
        default=None,
        description="Timestamp da última vez que a entrada foi observada.",
    )

    _normalize_mac = field_validator("mac_address", mode="before")(
        Interface._normalize_mac_address.__func__  # type: ignore[attr-defined]
    )


class MACEntry(BaseModel):
    """
    Entrada da tabela MAC (bridge/forwarding) — mapeamento L2 de MAC para
    porta física e VLAN.

    Fonte de dados:
        - MikroTik: ``/interface bridge host print``
        - SNMP: dot1dTpFdbTable / dot1qTpFdbTable
    """

    model_config = ConfigDict(str_strip_whitespace=True)

    mac_address: str = Field(
        ..., description="Endereço MAC do ativo."
    )
    interface: Optional[str] = Field(
        default=None,
        description="Porta/interface do switch onde o MAC foi aprendido.",
    )
    vlan_id: Optional[int] = Field(
        default=None, ge=1, le=4094,
        description="VLAN associada ao MAC nesta porta.",
    )
    switch_port: Optional[str] = Field(
        default=None,
        description="Identificador físico da porta do switch (ex: 'ether12', 'Gi0/1').",
    )
    vendor_oui: Optional[str] = Field(
        default=None,
        description="Fabricante inferido pelos 3 primeiros octetos do MAC (OUI).",
    )
    is_local: bool = Field(
        default=False,
        description="True se o MAC pertence ao próprio dispositivo (não aprendido).",
    )
    last_seen: Optional[datetime] = Field(
        default=None,
        description="Timestamp da última observação.",
    )

    _normalize_mac = field_validator("mac_address", mode="before")(
        Interface._normalize_mac_address.__func__  # type: ignore[attr-defined]
    )


class LLDPNeighbor(BaseModel):
    """
    Vizinho descoberto via LLDP, CDP ou protocolo de neighbor discovery.

    Fonte de dados:
        - MikroTik: ``/ip neighbor print detail``
        - SNMP: lldpRemTable (OID 1.0.8802.1.1.2.1.4)
    """

    model_config = ConfigDict(str_strip_whitespace=True)

    local_port: Optional[str] = Field(
        default=None,
        description="Porta local onde o vizinho foi descoberto.",
    )
    remote_device: Optional[str] = Field(
        default=None,
        description="Hostname/identity do vizinho remoto.",
    )
    remote_port: Optional[str] = Field(
        default=None,
        description="Porta do vizinho remoto conectada ao local.",
    )
    remote_ip: Optional[str] = Field(
        default=None,
        description="Endereço IP de gerência do vizinho.",
    )
    remote_mac: Optional[str] = Field(
        default=None,
        description="MAC address do vizinho.",
    )
    remote_platform: Optional[str] = Field(
        default=None,
        description="Fabricante/modelo/SO do vizinho (ex: 'MikroTik RB4011').",
    )
    remote_description: Optional[str] = Field(
        default=None,
        description="Texto descritivo do sistema remoto.",
    )

    _normalize_mac = field_validator("remote_mac", mode="before")(
        Interface._normalize_mac_address.__func__  # type: ignore[attr-defined]
    )


class TopologySnapshot(BaseModel):
    """
    Snapshot completo de topologia coletado de um dispositivo.
    Agrega tabelas ARP, MAC e vizinhos LLDP.
    """

    customer_id: str
    device_id: str
    collected_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
    )
    arp_table: list[ARPEntry] = Field(default_factory=list)
    mac_table: list[MACEntry] = Field(default_factory=list)
    lldp_neighbors: list[LLDPNeighbor] = Field(default_factory=list)


class NetworkNode(BaseModel):
    """
    Nó de rede correlacionado — visão unificada L2/L3 de um ativo.

    Resultado da fusão da tabela ARP (IP → MAC) com a tabela MAC
    (MAC → porta → VLAN). Representa um dispositivo na topologia.
    """

    model_config = ConfigDict(str_strip_whitespace=True)

    mac_address: str = Field(
        ..., description="Identificador primário de auditoria (mais estável que IP)."
    )
    ip_address: Optional[str] = Field(
        default=None, description="Endereço IPv4 (via ARP)."
    )
    hostname: Optional[str] = Field(
        default=None, description="Nome do host (se resolvido)."
    )
    vlan_id: Optional[int] = Field(
        default=None, ge=1, le=4094,
        description="VLAN onde o nó foi observado.",
    )
    switch_port: Optional[str] = Field(
        default=None, description="Porta física do switch (ex: 'ether12').",
    )
    vendor_oui: Optional[str] = Field(
        default=None, description="Fabricante inferido pelo OUI do MAC."
    )
    first_seen: Optional[datetime] = Field(
        default=None, description="Primeira vez que o nó foi observado."
    )
    last_seen: Optional[datetime] = Field(
        default=None, description="Última vez que o nó foi observado."
    )
    authorized: bool = Field(
        default=False,
        description="Se True, o nó está autorizado para as VLANs onde reside.",
    )

    _normalize_mac = field_validator("mac_address", mode="before")(
        Interface._normalize_mac_address.__func__  # type: ignore[attr-defined]
    )
