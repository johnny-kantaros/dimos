from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Message:
    role: str  # "user" | "assistant" | "tool"
    content: str
    tool_use_id: str | None = None
    tool_calls: list[dict[str, Any]] = field(default_factory=list)


class ChatSession:
    def __init__(self, session_id: str, robot_name: str) -> None:
        self.session_id = session_id
        self.robot_name = robot_name
        self.history: list[Message] = []
        self._lock = threading.Lock()

    def append(self, role: str, content: str, **kwargs: Any) -> None:
        with self._lock:
            self.history.append(Message(role=role, content=content, **kwargs))

    def get_history(self) -> list[Message]:
        with self._lock:
            return list(self.history)


class SessionStore:
    def __init__(self) -> None:
        self._sessions: dict[str, ChatSession] = {}
        self._lock = threading.RLock()

    def create(self, robot_name: str) -> ChatSession:
        session_id = str(uuid.uuid4())
        session = ChatSession(session_id=session_id, robot_name=robot_name)
        with self._lock:
            self._sessions[session_id] = session
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
