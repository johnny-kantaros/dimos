from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from dimensional_gateway.system_tools.base import SystemTool

if TYPE_CHECKING:
    from dimensional_gateway.session import ChatSession

_background_tasks: set[asyncio.Task] = set()


class ListModulesTool(SystemTool):
    name = "list_modules"
    description = "List all modules currently registered with the coordinator."
    parameters = {"type": "object", "properties": {}}

    async def run(self, session: ChatSession, args: dict) -> str:
        modules = await asyncio.to_thread(session.connection._source.list_module_names)
        return "\n".join(modules) if modules else "No modules registered."


class AddModuleTool(SystemTool):
    name = "add_module"
    description = "Add a module to the running robot by its registered name (e.g. 'keyboard-teleop'). The user must provide the name — available modules cannot be listed."
    parameters = {
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "Registered module name (e.g. 'keyboard-teleop')"},
        },
        "required": ["name"],
    }

    async def run(self, session: ChatSession, args: dict) -> str:
        await asyncio.to_thread(session.connection.run, args["name"])
        await asyncio.to_thread(session.skills._build_cache)
        return f"Module '{args['name']}' added."


class StopModuleTool(SystemTool):
    name = "stop_module"
    description = "Stop a module's main loop and close its RPC. The module remains registered and can be restarted."
    parameters = {
        "type": "object",
        "properties": {
            "module_name": {"type": "string", "description": "Module class name (e.g. 'DemoSensors')"},
        },
        "required": ["module_name"],
    }

    async def run(self, session: ChatSession, args: dict) -> str:
        module_name = args["module_name"]
        module = session.connection._source.get_module(module_name)
        await asyncio.to_thread(module.stop)
        session.robot.stopped_modules.add(module_name)
        return f"Module '{module_name}' stopped."


class RestartModuleTool(SystemTool):
    name = "restart_module"
    description = "Start or restart a module. Use this to bring a stopped module back online or to reload a running one."
    parameters = {
        "type": "object",
        "properties": {
            "module_name": {"type": "string", "description": "Module class name (e.g. 'DemoSensors')"},
            "reload_source": {"type": "boolean", "description": "Reload source code before restarting.", "default": True},
        },
        "required": ["module_name"],
    }

    async def run(self, session: ChatSession, args: dict) -> str:
        module_name = args["module_name"]
        stopped = session.robot.stopped_modules

        async def _restart() -> None:
            try:
                await asyncio.to_thread(
                    session.connection._source.restart_module_by_class_name,
                    module_name,
                    reload_source=args.get("reload_source", True),
                )
                stopped.discard(module_name)
            except Exception:
                pass

        task = asyncio.create_task(_restart())
        task.add_done_callback(_background_tasks.discard)
        _background_tasks.add(task)
        return f"Restarting '{module_name}' in the background — it will appear in active modules once ready."
