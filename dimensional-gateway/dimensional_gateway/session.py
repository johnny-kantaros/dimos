from __future__ import annotations

import asyncio
import threading
import uuid
from dataclasses import dataclass
from typing import TYPE_CHECKING

from dimos.porcelain.skills_proxy import SkillsProxy

if TYPE_CHECKING:
    from dimensional_gateway.robot_registry import Robot


@dataclass
class Message:
    role: str
    content: str


class ChatSession:
    def __init__(self, session_id: str, robot: Robot) -> None:
        self.session_id = session_id
        self.robot = robot
        self._skills = SkillsProxy(robot.connection._source)
        self._history: list[Message] = []
        self._lock = asyncio.Lock()

    @property
    def active_robot(self) -> str:
        return self.robot.info.name

    @property
    def connection(self):  # type: ignore[return]
        return self.robot.connection

    @property
    def skills(self) -> SkillsProxy:
        return self._skills

    async def append(self, role: str, content: str) -> None:
        async with self._lock:
            self._history.append(Message(role=role, content=content))

    async def history(self) -> list[Message]:
        async with self._lock:
            return list(self._history)


class SessionStore:
    def __init__(self) -> None:
        self._sessions: dict[str, ChatSession] = {}
        self._lock = threading.Lock()

    def create(self, robot: Robot) -> ChatSession:
        session = ChatSession(session_id=str(uuid.uuid4()), robot=robot)
        with self._lock:
            self._sessions[session.session_id] = session
        return session

    def get(self, session_id: str) -> ChatSession | None:
        with self._lock:
            return self._sessions.get(session_id)

    def delete(self, session_id: str) -> None:
        with self._lock:
            self._sessions.pop(session_id, None)

    def list_all(self) -> list[ChatSession]:
        with self._lock:
            return list(self._sessions.values())
