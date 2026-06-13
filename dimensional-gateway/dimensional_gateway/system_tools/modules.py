from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from dimensional_gateway.system_tools.base import SystemTool

if TYPE_CHECKING:
    from dimensional_gateway.session import ChatSession


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
        return f"Module '{args['name']}' added."


class StartModuleTool(SystemTool):
    name = "start_module"
    description = "Start a module's main loop and stream handlers."
    parameters = {
        "type": "object",
        "properties": {
            "module_name": {"type": "string", "description": "Module class name (e.g. 'DemoSensors')"},
        },
        "required": ["module_name"],
    }

    async def run(self, session: ChatSession, args: dict) -> str:
        module = session.connection._source.get_module(args["module_name"])
        await asyncio.to_thread(module.start)
        return f"Module '{args['module_name']}' started."


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
        module = session.connection._source.get_module(args["module_name"])
        await asyncio.to_thread(module.stop)
        return f"Module '{args['module_name']}' stopped."


class RestartModuleTool(SystemTool):
    name = "restart_module"
    description = "Restart a module in place, optionally reloading its source code. Reconnects streams and re-injects module refs."
    parameters = {
        "type": "object",
        "properties": {
            "module_name": {"type": "string", "description": "Module class name (e.g. 'DemoSensors')"},
            "reload_source": {"type": "boolean", "description": "Reload source code before restarting.", "default": True},
        },
        "required": ["module_name"],
    }

    async def run(self, session: ChatSession, args: dict) -> str:
        await asyncio.to_thread(
            session.connection._source.restart_module_by_class_name,
            args["module_name"],
            reload_source=args.get("reload_source", True),
        )
        return f"Module '{args['module_name']}' restarted."
