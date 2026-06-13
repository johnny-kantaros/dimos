from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from dimensional_gateway.system_tools.base import SystemTool

if TYPE_CHECKING:
    from dimensional_gateway.session import ChatSession


class BuildModuleTool(SystemTool):
    name = "build_module"
    description = "Run the one-time build step for a module (downloads, docker builds, etc.)."
    parameters = {
        "type": "object",
        "properties": {
            "module_name": {"type": "string", "description": "Module name to build"},
        },
        "required": ["module_name"],
    }

    async def run(self, session: ChatSession, args: dict) -> str:
        module = session.connection._source.get_module(args["module_name"])
        await asyncio.to_thread(module.build)
        return f"Module '{args['module_name']}' built."


class StartModuleTool(SystemTool):
    name = "start_module"
    description = "Start a module's main loop and stream handlers."
    parameters = {
        "type": "object",
        "properties": {
            "module_name": {"type": "string", "description": "Module name to start"},
        },
        "required": ["module_name"],
    }

    async def run(self, session: ChatSession, args: dict) -> str:
        module = session.connection._source.get_module(args["module_name"])
        await asyncio.to_thread(module.start)
        return f"Module '{args['module_name']}' started."


class StopModuleTool(SystemTool):
    name = "stop_module"
    description = "Stop a specific module."
    parameters = {
        "type": "object",
        "properties": {
            "module_name": {"type": "string", "description": "Module name to stop"},
        },
        "required": ["module_name"],
    }

    async def run(self, session: ChatSession, args: dict) -> str:
        module = session.connection._source.get_module(args["module_name"])
        await asyncio.to_thread(module.stop)
        return f"Module '{args['module_name']}' stopped."


class SetTransportTool(SystemTool):
    name = "set_transport"
    description = "Rewire a module stream to a different transport."
    parameters = {
        "type": "object",
        "properties": {
            "module_name": {"type": "string"},
            "stream_name": {"type": "string"},
            "transport": {"type": "string"},
        },
        "required": ["module_name", "stream_name", "transport"],
    }

    async def run(self, session: ChatSession, args: dict) -> str:
        module = session.connection._source.get_module(args["module_name"])
        await asyncio.to_thread(module.set_transport, args["stream_name"], args["transport"])
        return f"Transport set for '{args['module_name']}.{args['stream_name']}'."


class SetModuleRefTool(SystemTool):
    name = "set_module_ref"
    description = "Inject a reference to another module into a running module."
    parameters = {
        "type": "object",
        "properties": {
            "module_name": {"type": "string"},
            "ref_name": {"type": "string"},
            "ref_module": {"type": "string"},
        },
        "required": ["module_name", "ref_name", "ref_module"],
    }

    async def run(self, session: ChatSession, args: dict) -> str:
        module = session.connection._source.get_module(args["module_name"])
        ref = session.connection._source.get_module(args["ref_module"])
        await asyncio.to_thread(module.set_module_ref, args["ref_name"], ref)
        return f"Module ref '{args['ref_name']}' set on '{args['module_name']}'."
