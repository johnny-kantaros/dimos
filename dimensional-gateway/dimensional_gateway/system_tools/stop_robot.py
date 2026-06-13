from __future__ import annotations

from typing import TYPE_CHECKING

from dimensional_gateway.system_tools.base import SystemTool

if TYPE_CHECKING:
    from dimensional_gateway.session import ChatSession


class StopRobotTool(SystemTool):
    name = "stop_robot"
    description = "Stop all modules and close the robot connection."
    parameters = {"type": "object", "properties": {}}

    async def run(self, session: ChatSession, args: dict) -> str:
        session.connection.stop()
        return "Robot connection stopped."
