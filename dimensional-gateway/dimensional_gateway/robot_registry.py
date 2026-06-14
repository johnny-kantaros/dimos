from __future__ import annotations

import threading
from dataclasses import dataclass, field

from dimensional_gateway.discovery import RobotInfo
from dimos.porcelain.dimos import Dimos


@dataclass
class Robot:
    info: RobotInfo
    connection: Dimos | None = None
    stopped_modules: set[str] = field(default_factory=set)


class RobotRegistry:
    """Thread-safe registry of robots discovered via mDNS, with one shared connection per robot."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._robots: dict[str, Robot] = {}

    def add(self, robot: RobotInfo) -> None:
        with self._lock:
            if robot.name in self._robots:
                self._robots[robot.name].info = robot
            else:
                self._robots[robot.name] = Robot(info=robot)

    def remove(self, name: str) -> None:
        with self._lock:
            entry = self._robots.pop(name, None)
        if entry is not None and entry.connection is not None:
            try:
                entry.connection.stop()
            except Exception:
                pass

    def get(self, name: str) -> Robot | None:
        with self._lock:
            return self._robots.get(name)

    def list(self) -> list[RobotInfo]:
        with self._lock:
            return [r.info for r in self._robots.values()]

    def get_connection(self, name: str) -> Dimos:
        """Return the shared Dimos connection for `name`, creating it if needed."""
        with self._lock:
            robot = self._robots.get(name)
            if robot is None:
                raise KeyError(name)
            if robot.connection is None or not robot.connection.is_running:
                conn = Dimos.connect(lcm_url=robot.info.lcm_url)
                rpc_timeouts = conn._source._coord.rpc.rpc_timeouts
                rpc_timeouts["list_modules"] = 5.0
                rpc_timeouts["get_skills"] = 5.0
                rpc_timeouts["restart_module_by_class_name"] = 60.0
                robot.connection = conn
            return robot.connection

    def stop_all_connections(self) -> None:
        with self._lock:
            robots = list(self._robots.values())
        for robot in robots:
            if robot.connection is not None:
                try:
                    robot.connection.stop()
                except Exception:
                    pass
                robot.connection = None
