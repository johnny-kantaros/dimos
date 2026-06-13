from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from dimensional_gateway.session import ChatSession


class SystemTool(ABC):
    name: str
    description: str
    parameters: dict[str, Any]

    @classmethod
    def schema(cls) -> dict:
        return {
            "type": "function",
            "function": {
                "name": cls.name,
                "description": cls.description,
                "parameters": cls.parameters,
            },
        }

    @abstractmethod
    async def run(self, session: ChatSession, args: dict) -> str:
        raise NotImplementedError
