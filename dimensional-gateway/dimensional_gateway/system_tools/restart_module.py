from __future__ import annotations

from typing import TYPE_CHECKING

from dimensional_gateway.system_tools.base import SystemTool

if TYPE_CHECKING:
    from dimensional_gateway.session import ChatSession


class RestartModuleTool(SystemTool):
    name = "restart_module"
    description = "Restart a running module by class name, optionally reloading its source."
    parameters = {
        "type": "object",
        "properties": {
            "class_name": {"type": "string", "description": "Module class name (e.g. 'DemoRobotActions')"},
            "reload_source": {"type": "boolean", "description": "Reload source code before restarting.", "default": True},
        },
        "required": ["class_name"],
    }

    async def run(self, session: ChatSession, args: dict) -> str:
        session.connection._source.restart_module_by_class_name(
            args["class_name"], reload_source=args.get("reload_source", True)
        )
        return f"Module '{args['class_name']}' restarted."
