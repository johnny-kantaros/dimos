from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass, field


@dataclass
class Message:
    role: str
    content: str


@dataclass
class ChatSession:
    session_id: str
    active_robot: str
    _history: list[Message] = field(default_factory=list)
    _lock: asyncio.Lock = field(init=False)

    def __post_init__(self) -> None:
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

    def create(self, active_robot: str) -> ChatSession:
        session = ChatSession(session_id=str(uuid.uuid4()), active_robot=active_robot)
        self._sessions[session.session_id] = session
        return session

    def get(self, session_id: str) -> ChatSession | None:
        return self._sessions.get(session_id)

    def delete(self, session_id: str) -> None:
        self._sessions.pop(session_id, None)

    def list_all(self) -> list[ChatSession]:
        return list(self._sessions.values())
