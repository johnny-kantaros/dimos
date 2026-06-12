from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from zeroconf import ServiceBrowser, ServiceInfo, ServiceListener, Zeroconf

SERVICE_TYPE = "_dimensional._tcp.local."


@dataclass
class RobotInfo:
    name: str
    lcm_url: str
    robot_type: str
    version: str
    status: str
    blueprint: str
    address: str
    gateway_url: str = ""


class _Listener(ServiceListener):
    def __init__(
        self,
        on_add: Callable[[RobotInfo], None],
        on_remove: Callable[[str], None],
    ) -> None:
        self._on_add = on_add
        self._on_remove = on_remove

    def add_service(self, zc: Zeroconf, type_: str, name: str) -> None:
        info = zc.get_service_info(type_, name)
        if info is None:
            return
        props = {k.decode(): (v.decode() if v is not None else "") for k, v in info.properties.items()}
        robot_name = name.removesuffix(f".{type_}")
        address = info.parsed_addresses()[0] if info.parsed_addresses() else ""
        http_port = props.get("http_port", "8129")
        gateway_url = f"http://{address}:{http_port}" if address else ""
        self._on_add(
            RobotInfo(
                name=robot_name,
                lcm_url=props.get("lcm_url", ""),
                robot_type=props.get("robot_type", "unknown"),
                version=props.get("version", ""),
                status=props.get("status", "idle"),
                blueprint=props.get("blueprint", ""),
                address=address,
                gateway_url=gateway_url,
            )
        )

    def update_service(self, zc: Zeroconf, type_: str, name: str) -> None:
        self.add_service(zc, type_, name)

    def remove_service(self, zc: Zeroconf, type_: str, name: str) -> None:
        robot_name = name.removesuffix(f".{type_}")
        self._on_remove(robot_name)


class Discovery:
    """Runs an mDNS browser and keeps RobotRegistry up to date."""

    def __init__(
        self,
        on_add: Callable[[RobotInfo], None],
        on_remove: Callable[[str], None],
    ) -> None:
        self._zeroconf = Zeroconf()
        self._browser = ServiceBrowser(
            self._zeroconf, SERVICE_TYPE, _Listener(on_add, on_remove)
        )

    def close(self) -> None:
        self._zeroconf.close()
