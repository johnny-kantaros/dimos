from __future__ import annotations

from typing import TYPE_CHECKING

from dimensional_gateway.system_tools.base import SystemTool

if TYPE_CHECKING:
    from dimensional_gateway.session import ChatSession


class LoadBlueprintTool(SystemTool):
    name = "load_blueprint"
    description = "Load a new module onto the robot by blueprint name."
    parameters = {
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "Blueprint registry name (e.g. 'demo-robot-actions')"},
        },
        "required": ["name"],
    }

    async def run(self, session: ChatSession, args: dict) -> str:
        session.connection.run(args["name"])
        return f"Blueprint '{args['name']}' loaded."
