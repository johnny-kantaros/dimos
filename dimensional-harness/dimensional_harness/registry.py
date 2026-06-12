from __future__ import annotations

import threading

from dimensional_harness.discovery import RobotInfo


class RobotRegistry:
    """In-memory registry of robots discovered via mDNS."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._robots: dict[str, RobotInfo] = {}

    def add(self, robot: RobotInfo) -> None:
        with self._lock:
            self._robots[robot.name] = robot

    def remove(self, name: str) -> None:
        with self._lock:
            self._robots.pop(name, None)

    def get(self, name: str) -> RobotInfo | None:
        with self._lock:
            return self._robots.get(name)

    def list(self) -> list[RobotInfo]:
        with self._lock:
            return list(self._robots.values())
