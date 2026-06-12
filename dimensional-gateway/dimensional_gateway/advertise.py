from __future__ import annotations

import socket
from typing import Any

from zeroconf import ServiceInfo, Zeroconf

SERVICE_TYPE = "_dimensional._tcp.local."


def _local_ip() -> str:
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]


def _encode_properties(props: dict[str, str]) -> dict[bytes, bytes]:
    return {k.encode(): v.encode() for k, v in props.items()}


class GatewayAdvertiser:
    """Registers and maintains a mDNS service entry for this robot."""

    def __init__(self, robot_name: str, lcm_url: str, robot_type: str, version: str) -> None:
        self._robot_name = robot_name
        self._lcm_url = lcm_url
        self._robot_type = robot_type
        self._version = version
        self._zeroconf: Zeroconf | None = None
        self._info: ServiceInfo | None = None
        self._server: str = socket.gethostname() + ".local."
        self._addresses: list[bytes] = []
        self._port: int = 7667

    def start(self) -> None:
        ip = _local_ip()
        self._addresses = [socket.inet_aton(ip)]
        self._zeroconf = Zeroconf()
        self._info = ServiceInfo(
            SERVICE_TYPE,
            f"{self._robot_name}.{SERVICE_TYPE}",
            addresses=self._addresses,
            port=self._port,
            properties=_encode_properties(self._base_properties()),
            server=self._server,
        )
        self._zeroconf.register_service(self._info)

    def update(self, entry: dict[str, Any] | None) -> None:
        if self._zeroconf is None or self._info is None:
            return
        props = self._base_properties()
        if entry:
            props["status"] = "running"
            props["blueprint"] = entry.get("blueprint", "")
        else:
            props["status"] = "idle"
            props["blueprint"] = ""
        self._info = ServiceInfo(
            SERVICE_TYPE,
            f"{self._robot_name}.{SERVICE_TYPE}",
            addresses=self._addresses,
            port=self._port,
            properties=_encode_properties(props),
            server=self._server,
        )
        self._zeroconf.update_service(self._info)

    def stop(self) -> None:
        if self._zeroconf is None or self._info is None:
            return
        self._zeroconf.unregister_service(self._info)
        self._zeroconf.close()
        self._zeroconf = None
        self._info = None

    def _base_properties(self) -> dict[str, str]:
        return {
            "lcm_url": self._lcm_url,
            "robot_type": self._robot_type,
            "version": self._version,
            "status": "idle",
            "blueprint": "",
            "capabilities": "",
        }
