"""
core/services/discovery_service.py
Serviço de discovery de ativos via nmap.

Agnóstico à interface — usado pelo CLI e pela API web.
"""

from __future__ import annotations

import ipaddress
import shutil
import subprocess
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import UTC, datetime


class DiscoveryError(RuntimeError):
    """Erro de execução/validação do fluxo de discovery."""


@dataclass(slots=True)
class ScanOptions:
    """Opções de profundidade de varredura nmap."""

    ping_only: bool = True
    ports_fast: bool = False
    ports_extended: bool = False
    os_detection: bool = False
    service_version: bool = False


@dataclass(slots=True)
class DiscoverResult:
    """Resultado de uma execução de discovery."""

    network: str
    scanned_at: str
    hosts: list[dict[str, object]]
    total_hosts: int
    scan_options: ScanOptions = field(
        default_factory=ScanOptions
    )


def _normalize_network(
    network_input: str,
) -> ipaddress.IPv4Network:
    try:
        network = ipaddress.ip_network(
            network_input.strip(), strict=False
        )
    except ValueError as exc:
        raise DiscoveryError(
            "Faixa de rede inválida. "
            "Use CIDR, ex: 192.168.88.0/24"
        ) from exc

    if network.version != 4:
        raise DiscoveryError(
            "Apenas redes IPv4 são suportadas nesta fase."
        )

    if network.num_addresses > 4096:
        raise DiscoveryError(
            "Faixa muito ampla. "
            "Use no máximo /20 (até 4096 endereços)."
        )

    return network


def _parse_ports(
    host_node: ET.Element,
) -> list[str]:
    """Extrai portas abertas de um nó <host> do XML nmap."""
    open_ports: list[str] = []
    ports_node = host_node.find("ports")
    if ports_node is None:
        return open_ports
    for port in ports_node.findall("port"):
        state = port.find("state")
        if (
            state is None
            or state.attrib.get("state") != "open"
        ):
            continue
        portid = port.attrib.get("portid", "?")
        proto = port.attrib.get("protocol", "tcp")
        svc = port.find("service")
        svc_name = (
            svc.attrib.get("name", "")
            if svc is not None
            else ""
        )
        entry = (
            f"{portid}/{proto} ({svc_name})"
            if svc_name
            else f"{portid}/{proto}"
        )
        open_ports.append(entry)
    return open_ports


def _parse_os(
    host_node: ET.Element,
) -> str | None:
    """Extrai melhor match de SO de um nó <host>."""
    os_node = host_node.find("os")
    if os_node is None:
        return None
    best = os_node.find("osmatch")
    if best is None:
        return None
    name = best.attrib.get("name", "")
    accuracy = best.attrib.get("accuracy", "")
    return (
        f"{name} ({accuracy}%)"
        if accuracy
        else name or None
    )


def _parse_nmap_xml(
    xml_content: str,
) -> list[dict[str, object]]:
    try:
        root = ET.fromstring(xml_content)
    except ET.ParseError as exc:
        raise DiscoveryError(
            "Saída XML do nmap inválida."
        ) from exc

    hosts: list[dict[str, object]] = []
    for host in root.findall("host"):
        status = host.find("status")
        if (
            status is None
            or status.attrib.get("state") != "up"
        ):
            continue

        ipv4 = None
        mac = None
        vendor = None
        for addr in host.findall("address"):
            addr_type = addr.attrib.get("addrtype")
            if addr_type == "ipv4":
                ipv4 = addr.attrib.get("addr")
            elif addr_type == "mac":
                mac = addr.attrib.get("addr")
                vendor = addr.attrib.get("vendor")

        hostname = None
        hostnames = host.find("hostnames")
        if hostnames is not None:
            hostname_node = hostnames.find("hostname")
            if hostname_node is not None:
                hostname = hostname_node.attrib.get(
                    "name"
                )

        if ipv4:
            hosts.append(
                {
                    "ip": ipv4,
                    "hostname": hostname,
                    "mac": mac,
                    "vendor": vendor,
                    "ports": _parse_ports(host),
                    "os": _parse_os(host),
                }
            )

    return sorted(
        hosts, key=lambda item: str(item.get("ip") or "")
    )


def _build_command(
    nmap_bin: str,
    network: ipaddress.IPv4Network,
    opts: ScanOptions,
) -> list[str]:
    """Monta o comando nmap conforme opções de scan."""
    cmd = [nmap_bin, "-n"]

    needs_port_scan = (
        opts.ports_fast
        or opts.ports_extended
        or opts.service_version
    )

    if opts.os_detection:
        cmd.append("-O")

    if opts.service_version:
        cmd.append("-sV")

    if needs_port_scan:
        if opts.ports_extended:
            cmd.extend(["--top-ports", "1000"])
        else:
            cmd.append("-F")
    elif not opts.os_detection:
        cmd.append("-sn")

    cmd.extend([str(network), "-oX", "-"])
    return cmd


def run_nmap_discovery(
    network_input: str,
    options: ScanOptions | None = None,
    timeout_seconds: int = 120,
) -> DiscoverResult:
    """Executa discovery nmap com opções configuráveis."""
    nmap_bin = shutil.which("nmap")
    if not nmap_bin:
        raise DiscoveryError(
            "Comando 'nmap' não encontrado no ambiente."
        )

    opts = options or ScanOptions()
    network = _normalize_network(network_input)
    command = _build_command(nmap_bin, network, opts)

    try:
        proc = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired as exc:
        raise DiscoveryError(
            "Timeout no discovery. "
            "Tente uma faixa menor."
        ) from exc

    if proc.returncode != 0:
        stderr = (
            (proc.stderr or "").strip()
            or "Erro desconhecido ao executar nmap."
        )
        raise DiscoveryError(f"Falha no nmap: {stderr}")

    hosts = _parse_nmap_xml(proc.stdout)
    scanned_at = datetime.now(UTC).isoformat(
        timespec="seconds"
    )

    return DiscoverResult(
        network=str(network),
        scanned_at=scanned_at,
        hosts=hosts,
        total_hosts=len(hosts),
        scan_options=opts,
    )
