from __future__ import annotations

import asyncio
import json
from typing import Any, AsyncIterator

import openai

from dimensional_gateway.prompts import build_system_message
from dimensional_gateway.session import ChatSession
from dimensional_gateway.system_tools import SYSTEM_TOOLS

_client = openai.AsyncOpenAI()
_MODEL = "gpt-4o"

_MAX_STEPS = 20


def _build_robot_tools(session: ChatSession) -> list[dict]:
    skills = session.skills
    skills._build_cache()
    if not skills._cache:
        return []

    tools = []
    for name, entries in skills._cache.items():
        _, _, info = entries[0]
        schema = json.loads(info.args_schema)
        description = schema.get("description") or f"Execute {name} on {session.active_robot}"
        tools.append({
            "type": "function",
            "function": {"name": name, "description": description, "parameters": schema},
        })
    return tools


def _build_system_tools() -> list[dict]:
    return [cls.schema() for cls in SYSTEM_TOOLS.values()]


def _build_tools(session: ChatSession) -> list[dict]:
    return _build_robot_tools(session) + _build_system_tools()


async def _dispatch_tool(session: ChatSession, name: str, args: dict) -> str:
    tool_cls = SYSTEM_TOOLS.get(name)
    if tool_cls is not None:
        return await tool_cls().run(session, args)
    return str(await asyncio.to_thread(lambda: getattr(session.skills, name)(**args)))


async def _call_tool(session: ChatSession, tc: Any) -> dict:
    try:
        args = json.loads(tc.function.arguments)
        content = await _dispatch_tool(session, tc.function.name, args)
    except Exception as exc:
        content = f"Error: {exc}"
    return {"role": "tool", "tool_call_id": tc.id, "content": content}


async def run_agent(session: ChatSession) -> AsyncIterator[str]:
    tools = await asyncio.to_thread(_build_tools, session)
    module_names = session.connection._source.list_module_names()

    history = await session.history()
    messages: list = [
        build_system_message(session, module_names),
        *[{"role": m.role, "content": m.content} for m in history],
    ]
    final_response = ""

    for _ in range(_MAX_STEPS):
        async with _client.chat.completions.stream(
            model=_MODEL,
            messages=messages,
            tools=tools,
        ) as stream:
            async for chunk in stream:
                delta = chunk.choices[0].delta
                if delta.content:
                    final_response += delta.content
                    yield f"data: {delta.content}\n\n"
            response = await stream.get_final_completion()

        choice = response.choices[0]
        if choice.finish_reason != "tool_calls":
            break

        messages.append(choice.message.model_dump(exclude_none=True))
        tool_calls = choice.message.tool_calls or []
        tool_results = await asyncio.gather(*[_call_tool(session, tc) for tc in tool_calls])
        messages.extend(tool_results)

    if final_response:
        await session.append("assistant", final_response)
    yield "data: [DONE]\n\n"
