from __future__ import annotations

from typing import TYPE_CHECKING

from dimensional_gateway.system_tools.base import SystemTool

if TYPE_CHECKING:
    from dimensional_gateway.session import ChatSession


class PeekStreamTool(SystemTool):
    name = "peek_stream"
    description = "Read the latest value from a named sensor or data stream on the robot."
    parameters = {
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "Stream name (e.g. 'color_image', 'imu')"},
            "timeout": {"type": "number", "description": "Seconds to wait for a value.", "default": 1.0},
        },
        "required": ["name"],
    }

    async def run(self, session: ChatSession, args: dict) -> str:
        result = session.connection.peek_stream(args["name"], args.get("timeout", 1.0))
        return str(result)
