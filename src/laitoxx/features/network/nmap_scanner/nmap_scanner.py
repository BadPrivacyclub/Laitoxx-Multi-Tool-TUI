from __future__ import annotations

import ctypes
import os
import platform
import shutil
import subprocess
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import Any

DEFAULT_PORTS = "1-1024"
DEFAULT_PROFILE = "quick"
SCAN_TIMEOUT_SECONDS = 180
ROOT_REQUIRED_ARGS = {"-O", "-sS", "-sU", "--privileged"}

SCAN_PROFILES: dict[str, tuple[str, ...]] = {
    "quick": ("-sV", "--open", "-T3"),
    "top100": ("--top-ports", "100", "-sV", "--open", "-T3"),
    "service": ("-sV", "-sC", "--open", "-T3"),
    "ping": ("-sn",),
}


@dataclass(frozen=True)
class NmapEnvironment:
    nmap_bin: str
    is_root: bool
    requires_root: bool
    platform_name: str


@dataclass(frozen=True)
class NmapPort:
    port: str
    protocol: str
    state: str
    service: str
    product: str
    version: str


@dataclass(frozen=True)
class NmapHost:
    address: str
    hostname: str
    state: str
    ports: tuple[NmapPort, ...]


def nmap_scanner_tool(config: dict[str, Any] | None = None) -> dict[str, Any] | None:
    """Run Nmap CLI and print a compact scan report."""
    config = config or _read_interactive_config()
    target = str(config.get("target", "")).strip()
    ports = str(config.get("ports", DEFAULT_PORTS)).strip() or DEFAULT_PORTS
    profile = str(config.get("profile", DEFAULT_PROFILE)).strip() or DEFAULT_PROFILE

    if not target:
        print("Error: target is required.")
        return None

    environment = check_nmap_environment(profile)
    if environment.nmap_bin == "":
        print("Error: nmap executable not found. Install Nmap and make sure 'nmap' is in PATH.")
        return None
    if environment.requires_root and not environment.is_root:
        print("Error: selected Nmap profile requires root/admin privileges.")
        return None

    command = build_nmap_command(environment.nmap_bin, target=target, ports=ports, profile=profile)
    print(
        "Nmap environment: "
        f"platform={environment.platform_name}, "
        f"root/admin={'yes' if environment.is_root else 'no'}"
    )
    print("Running: " + " ".join(command))

    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=SCAN_TIMEOUT_SECONDS,
            check=False,
        )
    except subprocess.TimeoutExpired:
        print(f"Error: scan timed out after {SCAN_TIMEOUT_SECONDS} seconds.")
        return None

    if completed.returncode != 0:
        stderr = completed.stderr.strip() or completed.stdout.strip() or "unknown nmap error"
        print(f"Error: nmap exited with code {completed.returncode}: {stderr}")
        return None

    hosts = parse_nmap_xml(completed.stdout)
    print_nmap_report(hosts)
    return {
        "target": target,
        "profile": profile,
        "ports": ports,
        "hosts": hosts,
    }


def check_nmap_environment(profile: str = DEFAULT_PROFILE) -> NmapEnvironment:
    """Return Nmap executable and privilege state for the selected profile."""
    profile_args = SCAN_PROFILES.get(profile, SCAN_PROFILES[DEFAULT_PROFILE])
    return NmapEnvironment(
        nmap_bin=shutil.which("nmap") or "",
        is_root=_has_admin_privileges(),
        requires_root=any(arg in ROOT_REQUIRED_ARGS for arg in profile_args),
        platform_name=platform.system() or "unknown",
    )


def _has_admin_privileges() -> bool:
    if os.name == "nt":
        try:
            return bool(ctypes.windll.shell32.IsUserAnAdmin())
        except (AttributeError, OSError):
            return False
    if hasattr(os, "geteuid"):
        return os.geteuid() == 0
    return False


def build_nmap_command(nmap_bin: str, *, target: str, ports: str, profile: str) -> list[str]:
    profile_args = list(SCAN_PROFILES.get(profile, SCAN_PROFILES[DEFAULT_PROFILE]))
    command = [nmap_bin, "-oX", "-"]

    if "-sn" not in profile_args and ports:
        command.extend(["-p", ports])

    command.extend(profile_args)
    command.append(target)
    return command


def parse_nmap_xml(xml_text: str) -> list[NmapHost]:
    root = ET.fromstring(xml_text)
    hosts: list[NmapHost] = []

    for host_node in root.findall("host"):
        address = _host_address(host_node)
        hostname = _host_name(host_node)
        state = _host_state(host_node)
        ports = tuple(_iter_ports(host_node))
        hosts.append(NmapHost(address=address, hostname=hostname, state=state, ports=ports))

    return hosts


def print_nmap_report(hosts: list[NmapHost]) -> None:
    if not hosts:
        print("No hosts returned by Nmap.")
        return

    for host in hosts:
        title = host.address if not host.hostname else f"{host.address} ({host.hostname})"
        print(f"\nHost: {title}")
        print(f"State: {host.state}")

        if not host.ports:
            print("Open ports: none")
            continue

        print("Port     Proto  State   Service")
        print("-----------------------------------------------")
        for port in host.ports:
            service = port.service
            details = " ".join(part for part in (port.product, port.version) if part)
            if details:
                service = f"{service} ({details})" if service else details
            print(f"{port.port:<8} {port.protocol:<6} {port.state:<7} {service}")


def _read_interactive_config() -> dict[str, str]:
    target = input("Target host/IP/network: ").strip()
    ports = input(f"Ports [{DEFAULT_PORTS}]: ").strip() or DEFAULT_PORTS
    profile = input("Profile quick/top100/service/ping [quick]: ").strip() or DEFAULT_PROFILE
    return {"target": target, "ports": ports, "profile": profile}


def _host_address(host_node: ET.Element) -> str:
    address_node = host_node.find("address")
    return address_node.get("addr", "") if address_node is not None else ""


def _host_name(host_node: ET.Element) -> str:
    hostname_node = host_node.find("hostnames/hostname")
    return hostname_node.get("name", "") if hostname_node is not None else ""


def _host_state(host_node: ET.Element) -> str:
    status_node = host_node.find("status")
    return status_node.get("state", "unknown") if status_node is not None else "unknown"


def _iter_ports(host_node: ET.Element):
    for port_node in host_node.findall("ports/port"):
        state_node = port_node.find("state")
        service_node = port_node.find("service")
        yield NmapPort(
            port=port_node.get("portid", ""),
            protocol=port_node.get("protocol", ""),
            state=state_node.get("state", "unknown") if state_node is not None else "unknown",
            service=service_node.get("name", "") if service_node is not None else "",
            product=service_node.get("product", "") if service_node is not None else "",
            version=service_node.get("version", "") if service_node is not None else "",
        )


if __name__ == "__main__":
    nmap_scanner_tool()
