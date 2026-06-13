from __future__ import annotations

import json
from typing import TYPE_CHECKING

from dimensional_gateway.system_tools.base import SystemTool

if TYPE_CHECKING:
    from dimensional_gateway.session import ChatSession


class ListModulesTool(SystemTool):
    name = "list_modules"
    description = "List all modules currently running on the robot."
    parameters = {"type": "object", "properties": {}}

    async def run(self, session: ChatSession, args: dict) -> str:
        modules = session.connection._source.list_module_names()
        return json.dumps({"modules": modules})
