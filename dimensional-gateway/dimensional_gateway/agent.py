from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
import functools
import json

import openai

from dimensional_gateway.prompts import build_system_message
from dimensional_gateway.session import ChatSession
from dimensional_gateway.system_tools import SYSTEM_TOOLS

_client = openai.AsyncOpenAI()
_MODEL = "gpt-4o"

_MAX_STEPS = 20


_STATUS_PARAM = {
    "type": "string",
    "description": "One short sentence shown to the user before this tool runs (e.g. 'Checking active modules...')",
}


def _add_status_param(tool: dict) -> dict:
    """Inject _status as a required parameter into every tool schema.

    Rather than relying on the system prompt to ask the LLM to narrate its actions
    (which it reliably ignores), making _status a required field in the schema forces
    the model to provide a progress message on every call. We extract and stream it
    before dispatch, then discard it so individual tools never see it.
    """
    params = tool["function"]["parameters"]
    return {
        **tool,
        "function": {
            **tool["function"],
            "parameters": {
                **params,
                "properties": {**params.get("properties", {}), "_status": _STATUS_PARAM},
                "required": [*params.get("required", []), "_status"],
            },
        },
    }


@functools.cache
def _build_system_tools() -> list[dict]:
    return [_add_status_param(cls.schema()) for cls in SYSTEM_TOOLS.values()]


def _fetch_robot_context(session: ChatSession) -> tuple[list[dict], list[str]]:
    stopped = session.robot.stopped_modules
    robot_tools: list[dict] = []
    active_names: set[str] = set()

    for skill_name, entries in (session.skills._cache or {}).items():
        for class_name, _, info in entries:
            if class_name in stopped:
                continue
            schema = json.loads(info.args_schema)
            description = schema.get("description") or f"Execute {skill_name} on {session.active_robot}"
            robot_tools.append(_add_status_param({
                "type": "function",
                "function": {"name": skill_name, "description": description, "parameters": schema},
            }))
            active_names.add(class_name)

    return robot_tools, sorted(active_names)


async def _dispatch_tool(session: ChatSession, name: str, args: dict) -> str:
    tool_cls = SYSTEM_TOOLS.get(name)
    if tool_cls is not None:
        return await tool_cls().run(session, args)
    return str(await asyncio.to_thread(lambda: getattr(session.skills, name)(**args)))


def _event(event_type: str, **kwargs: object) -> str:
    return f"data: {json.dumps({'type': event_type, **kwargs})}\n\n"


async def _call_tool(session: ChatSession, tc_id: str, name: str, args: dict) -> dict:
    try:
        content = await _dispatch_tool(session, name, args)
    except Exception as exc:
        content = f"Error: {exc}"
    return {"role": "tool", "tool_call_id": tc_id, "content": content}


async def run_agent(session: ChatSession) -> AsyncIterator[str]:
    robot_tools, module_names = _fetch_robot_context(session)
    tools = robot_tools + _build_system_tools()

    history = await session.history()
    messages: list = [
        build_system_message(session, module_names),
        *[{"role": m.role, "content": m.content} for m in history],
    ]
    final_response = ""

    for _ in range(_MAX_STEPS):
        finish_reason = None
        tool_calls_acc: dict[int, dict] = {}
        step_text = ""

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
                step_text += delta.content
                final_response += delta.content
                yield _event("token", content=delta.content)

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

        parsed: list[tuple[dict, dict]] = []
        error_results: list[dict] = []
        for tc in tool_calls:
            try:
                args = json.loads(tc["function"]["arguments"])
            except json.JSONDecodeError as exc:
                error_results.append({"role": "tool", "tool_call_id": tc["id"], "content": f"Error: {exc}"})
                continue
            if (status := args.pop("_status", None)) is not None:
                yield _event("status", content=status)
            parsed.append((tc, args))

        messages.append({
            "role": "assistant",
            "content": step_text or None,
            "tool_calls": tool_calls,
        })

        gathered = await asyncio.gather(*[
            _call_tool(session, tc["id"], tc["function"]["name"], args)
            for tc, args in parsed
        ])
        messages.extend(error_results + list(gathered))
        yield _event("thinking")

    if final_response:
        await session.append("assistant", final_response)
    yield "data: [DONE]\n\n"
