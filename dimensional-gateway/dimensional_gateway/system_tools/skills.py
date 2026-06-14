from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from dimensional_gateway.skills_store import load_skill, save_skill
from dimensional_gateway.system_tools.base import SystemTool

if TYPE_CHECKING:
    from dimensional_gateway.session import ChatSession


class LoadSkillTool(SystemTool):
    name = "load_skill"
    description = "Load a skill by name to get its step-by-step instructions, then follow them. Robot-specific skills take priority over system-level ones."
    parameters = {
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "Skill name (from list_skills)"},
        },
        "required": ["name"],
    }

    async def run(self, session: ChatSession, args: dict) -> str:
        content = await asyncio.to_thread(load_skill, args["name"], session.active_robot)
        if content is None:
            return f"Skill '{args['name']}' not found. Use list_skills to see available skills."
        return content


class SaveSkillTool(SystemTool):
    name = "save_skill"
    description = (
        "Save a new skill or overwrite an existing one. "
        "Saves to the current robot by default; set system=true to save for all robots."
    )
    parameters = {
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "Skill name (snake_case, no spaces)"},
            "description": {"type": "string", "description": "One-line summary of what the skill does"},
            "steps": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Ordered list of steps the agent should follow",
            },
            "instructions": {"type": "string", "description": "Optional context or notes for the agent"},
            "system": {"type": "boolean", "description": "Save as a system-level skill available to all robots.", "default": False},
        },
        "required": ["name", "description", "steps"],
    }

    async def run(self, session: ChatSession, args: dict) -> str:
        robot = None if args.get("system") else session.active_robot
        data: dict = {"description": args["description"], "steps": args["steps"]}
        if instructions := args.get("instructions"):
            data["instructions"] = instructions
        await asyncio.to_thread(save_skill, args["name"], data, robot)
        scope = "system" if robot is None else session.active_robot
        return f"Skill '{args['name']}' saved ({scope})."
