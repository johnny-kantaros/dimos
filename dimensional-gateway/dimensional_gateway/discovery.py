from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from zeroconf import ServiceBrowser, ServiceListener, Zeroconf

SERVICE_TYPE = "_dimensional._tcp.local."


@dataclass
class RobotInfo:
    name: str
    lcm_url: str
    address: str


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
        props = {
            k.decode(errors="replace"): (v.decode(errors="replace") if v else "")
            for k, v in info.properties.items()
        }
        robot_name = name.removesuffix(f".{type_}")
        addresses = info.parsed_addresses()
        address = addresses[0] if addresses else ""
        self._on_add(RobotInfo(
            name=robot_name,
            lcm_url=props.get("lcm_url", ""),
            address=address,
        ))

    def update_service(self, zc: Zeroconf, type_: str, name: str) -> None:
        self.add_service(zc, type_, name)

    def remove_service(self, zc: Zeroconf, type_: str, name: str) -> None:
        self._on_remove(name.removesuffix(f".{type_}"))


class Discovery:
    """Runs an mDNS browser and keeps RobotRegistry up to date."""

    def __init__(
        self,
        on_add: Callable[[RobotInfo], None],
        on_remove: Callable[[str], None],
    ) -> None:
        self._zeroconf = Zeroconf()
        self._browser = ServiceBrowser(self._zeroconf, SERVICE_TYPE, _Listener(on_add, on_remove))

    def close(self) -> None:
        self._zeroconf.close()
