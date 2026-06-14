from __future__ import annotations

from dimensional_gateway.system_tools.base import SystemTool
from dimensional_gateway.system_tools.modules import (
    AddModuleTool,
    ListModulesTool,
    RestartModuleTool,
    StopModuleTool,
)
from dimensional_gateway.system_tools.peek_stream import PeekStreamTool
from dimensional_gateway.system_tools.skills import LoadSkillTool, SaveSkillTool

SYSTEM_TOOLS: dict[str, type[SystemTool]] = {
    cls.name: cls
    for cls in [
        ListModulesTool,
        AddModuleTool,
        StopModuleTool,
        RestartModuleTool,
        PeekStreamTool,
        LoadSkillTool,
        SaveSkillTool,
    ]
}
