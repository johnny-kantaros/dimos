from __future__ import annotations

import threading

from dimos.porcelain.dimos import Dimos


class RobotConnection:
    """Holds a single Dimos connection to one robot, shared across sessions."""

    def __init__(self, robot_name: str, lcm_url: str, timeout: float = 5.0) -> None:
        self.robot_name = robot_name
        self.lcm_url = lcm_url
        self._timeout = timeout
        self._app: Dimos | None = None
        self._lock = threading.Lock()

    def acquire(self) -> Dimos:
        with self._lock:
            if self._app is None or not self._app.is_running:
                self._app = Dimos.connect(lcm_url=self.lcm_url, timeout=self._timeout)
            return self._app

    def close(self) -> None:
        with self._lock:
            if self._app is not None:
                self._app.stop()
                self._app = None


class ConnectionPool:
    """One RobotConnection per robot name, created on first use."""

    def __init__(self) -> None:
        self._connections: dict[str, RobotConnection] = {}
        self._lock = threading.RLock()

    def get(self, robot_name: str, lcm_url: str) -> RobotConnection:
        with self._lock:
            if robot_name not in self._connections:
                self._connections[robot_name] = RobotConnection(robot_name, lcm_url)
            return self._connections[robot_name]

    def close_all(self) -> None:
        with self._lock:
            for conn in self._connections.values():
                conn.close()
            self._connections.clear()
