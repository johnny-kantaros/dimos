from __future__ import annotations

from openai.types.chat import ChatCompletionSystemMessageParam

from dimensional_gateway.session import ChatSession

_SYSTEM = (
    "You are an AI agent controlling a robot. "
    "Use the provided tools to execute robot skills. "
    "After calling a skill, always tell the user what happened."
)


def build_system_message(session: ChatSession) -> ChatCompletionSystemMessageParam:
    # TODO: append additional robot + user context
    return ChatCompletionSystemMessageParam(
        role="system",
        content=f"{_SYSTEM}\n\nRobot name: {session.active_robot}",
    )
