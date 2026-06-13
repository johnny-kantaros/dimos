from __future__ import annotations

import asyncio
import json
from typing import AsyncIterator

import openai

from dimensional_gateway.prompts import build_system_message
from dimensional_gateway.session import ChatSession
from dimensional_gateway.system_tools import SYSTEM_TOOLS

_client = openai.AsyncOpenAI()
_MODEL = "gpt-4o"

_MAX_STEPS = 20


def _build_system_tools() -> list[dict]:
    return [cls.schema() for cls in SYSTEM_TOOLS.values()]


def _fetch_robot_context(session: ChatSession) -> tuple[list[dict], list[str]]:
    """Return (tools, module_names) from a single _build_cache() call.

    Avoids a redundant coordinator RPC and keeps module_names consistent with
    the tool list. Must run in a thread as _build_cache() blocks on LCM RPC.
    """
    skills = session.skills
    robot_tools: list[dict] = []
    module_names: list[str] = []

    try:
        skills._build_cache()
        module_names = list(skills._cache_key or [])
        for name, entries in (skills._cache or {}).items():
            _, _, info = entries[0]
            schema = json.loads(info.args_schema)
            description = schema.get("description") or f"Execute {name} on {session.active_robot}"
            robot_tools.append({
                "type": "function",
                "function": {"name": name, "description": description, "parameters": schema},
            })
    except Exception:
        pass

    return robot_tools + _build_system_tools(), module_names


async def _dispatch_tool(session: ChatSession, name: str, args: dict) -> str:
    tool_cls = SYSTEM_TOOLS.get(name)
    if tool_cls is not None:
        return await tool_cls().run(session, args)
    return str(await asyncio.to_thread(lambda: getattr(session.skills, name)(**args)))


async def _call_tool(session: ChatSession, tc_id: str, name: str, arguments: str) -> dict:
    try:
        args = json.loads(arguments)
        content = await _dispatch_tool(session, name, args)
    except Exception as exc:
        content = f"Error: {exc}"
    return {"role": "tool", "tool_call_id": tc_id, "content": content}


async def run_agent(session: ChatSession) -> AsyncIterator[str]:
    tools, module_names = await asyncio.to_thread(_fetch_robot_context, session)

    history = await session.history()
    messages: list = [
        build_system_message(session, module_names),
        *[{"role": m.role, "content": m.content} for m in history],
    ]
    final_response = ""

    for _ in range(_MAX_STEPS):
        finish_reason = None
        tool_calls_acc: dict[int, dict] = {}

        stream = await _client.chat.completions.create(
            model=_MODEL,
            messages=messages,
            tools=tools,
            stream=True,
        )

        async for chunk in stream:
            choice = chunk.choices[0]
            if choice.finish_reason:
                finish_reason = choice.finish_reason

            delta = choice.delta
            if delta.content:
                final_response += delta.content
                yield f"data: {json.dumps(delta.content)}\n\n"

            for tc in delta.tool_calls or []:
                if tc.index not in tool_calls_acc:
                    tool_calls_acc[tc.index] = {
                        "id": tc.id,
                        "type": "function",
                        "function": {"name": tc.function.name or "", "arguments": ""},
                    }
                if tc.function.arguments:
                    tool_calls_acc[tc.index]["function"]["arguments"] += tc.function.arguments

        if finish_reason != "tool_calls":
            break

        tool_calls = list(tool_calls_acc.values())
        messages.append({
            "role": "assistant",
            "content": final_response or None,
            "tool_calls": tool_calls,
        })
        tool_results = await asyncio.gather(*[
            _call_tool(session, tc["id"], tc["function"]["name"], tc["function"]["arguments"])
            for tc in tool_calls
        ])
        messages.extend(tool_results)

    if final_response:
        await session.append("assistant", final_response)
    yield "data: [DONE]\n\n"
