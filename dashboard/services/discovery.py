"""Serviço de discovery de ativos via nmap."""

from __future__ import annotations

import ipaddress
import shutil
import subprocess
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import UTC, datetime


class DiscoveryError(RuntimeError):
    """Erro de execução/validação do fluxo de discovery."""


@dataclass(slots=True)
class DiscoverResult:
    """Resultado de uma execução de discovery."""

    network: str
    scanned_at: str
    hosts: list[dict[str, str | None]]
    total_hosts: int


def _normalize_network(network_input: str) -> ipaddress.IPv4Network:
    try:
        network = ipaddress.ip_network(network_input.strip(), strict=False)
    except ValueError as exc:
        raise DiscoveryError("Faixa de rede inválida. Use CIDR, ex: 192.168.88.0/24") from exc

    if network.version != 4:
        raise DiscoveryError("Apenas redes IPv4 são suportadas nesta fase.")

    if network.num_addresses > 4096:
        raise DiscoveryError("Faixa muito ampla. Use no máximo /20 (até 4096 endereços).")

    return network


def _parse_nmap_xml(xml_content: str) -> list[dict[str, str | None]]:
    try:
        root = ET.fromstring(xml_content)
    except ET.ParseError as exc:
        raise DiscoveryError("Saída XML do nmap inválida.") from exc

    hosts: list[dict[str, str | None]] = []
    for host in root.findall("host"):
        status = host.find("status")
        if status is None or status.attrib.get("state") != "up":
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
                hostname = hostname_node.attrib.get("name")

        if ipv4:
            hosts.append({
                "ip": ipv4,
                "hostname": hostname,
                "mac": mac,
                "vendor": vendor,
            })

    return sorted(hosts, key=lambda item: item["ip"] or "")


def run_nmap_discovery(network_input: str, timeout_seconds: int = 120) -> DiscoverResult:
    """Executa discovery por ping scan (`nmap -sn`) em uma faixa de rede."""
    nmap_bin = shutil.which("nmap")
    if not nmap_bin:
        raise DiscoveryError("Comando 'nmap' não encontrado no ambiente.")

    network = _normalize_network(network_input)
    command = [nmap_bin, "-sn", "-n", str(network), "-oX", "-"]

    try:
        proc = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired as exc:
        raise DiscoveryError("Timeout no discovery. Tente uma faixa menor.") from exc

    if proc.returncode != 0:
        stderr = (proc.stderr or "").strip() or "Erro desconhecido ao executar nmap."
        raise DiscoveryError(f"Falha no nmap: {stderr}")

    hosts = _parse_nmap_xml(proc.stdout)
    scanned_at = datetime.now(UTC).isoformat(timespec="seconds")

    return DiscoverResult(
        network=str(network),
        scanned_at=scanned_at,
        hosts=hosts,
        total_hosts=len(hosts),
    )
