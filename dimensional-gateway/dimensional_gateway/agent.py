from __future__ import annotations

import asyncio
import json
from typing import AsyncIterator

import anthropic

from dimensional_gateway.session import ChatSession

_client = anthropic.AsyncAnthropic()
_MODEL = "claude-opus-4-8"

_SYSTEM_PREFIX = (
    "You are an AI agent controlling a robot. "
    "Use the provided tools to execute robot skills. "
    "After calling a skill, always tell the user what happened."
)


def _build_tools(session: ChatSession) -> list[dict]:
    skills = session.skills
    skills._build_cache()
    if not skills._cache:
        return []

    tools = []
    for name, entries in skills._cache.items():
        _, _, info = entries[0]
        schema = json.loads(info.args_schema)
        description = schema.get("description") or f"Execute {name} on {session.active_robot}"
        tools.append({"name": name, "description": description, "input_schema": schema})
    return tools


async def run_agent(session: ChatSession, message: str) -> AsyncIterator[str]:
    history = await session.history()
    messages = [{"role": m.role, "content": m.content} for m in history]
    system = f"{_SYSTEM_PREFIX}\n\nRobot name: {session.active_robot}"

    tools = await asyncio.to_thread(_build_tools, session)

    full_reply_parts: list[str] = []

    while True:
        kwargs: dict = {
            "model": _MODEL,
            "max_tokens": 4096,
            "system": system,
            "messages": messages,
        }
        if tools:
            kwargs["tools"] = tools

        async with _client.messages.stream(**kwargs) as stream:
            async for text in stream.text_stream:
                full_reply_parts.append(text)
                yield f"data: {text}\n\n"
            response = await stream.get_final_message()

        if response.stop_reason != "tool_use":
            break

        tool_use_blocks = [b for b in response.content if b.type == "tool_use"]
        messages.append({"role": "assistant", "content": response.content})

        tool_results = []
        for block in tool_use_blocks:
            try:
                result = await asyncio.to_thread(
                    lambda b=block: getattr(session.skills, b.name)(**b.input)
                )
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": str(result),
                })
            except Exception as exc:
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": f"Error: {exc}",
                    "is_error": True,
                })

        messages.append({"role": "user", "content": tool_results})

    await session.append("assistant", "".join(full_reply_parts))
    yield "data: [DONE]\n\n"
