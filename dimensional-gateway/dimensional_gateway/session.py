from __future__ import annotations

import asyncio
import threading
import uuid
from dataclasses import dataclass

from dimos.porcelain.dimos import Dimos


@dataclass
class Message:
    role: str
    content: str


class ChatSession:
    def __init__(self, session_id: str, active_robot: str, connection: Dimos) -> None:
        self.session_id = session_id
        self.active_robot = active_robot
        self.connection = connection
        self._history: list[Message] = []
        self._lock = asyncio.Lock()

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

    def create(self, active_robot: str, connection: Dimos) -> ChatSession:
        session = ChatSession(
            session_id=str(uuid.uuid4()),
            active_robot=active_robot,
            connection=connection,
        )
        with self._lock:
            self._sessions[session.session_id] = session
        return session

    def get(self, session_id: str) -> ChatSession | None:
        with self._lock:
            return self._sessions.get(session_id)

    def delete(self, session_id: str) -> None:
        with self._lock:
            session = self._sessions.pop(session_id, None)
        if session is not None:
            session.connection.stop()

    def stop_all(self) -> None:
        with self._lock:
            sessions = list(self._sessions.values())
            self._sessions.clear()
        for session in sessions:
            session.connection.stop()

    def list_all(self) -> list[ChatSession]:
        with self._lock:
            return list(self._sessions.values())
