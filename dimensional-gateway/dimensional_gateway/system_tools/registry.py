from __future__ import annotations

from dimensional_gateway.system_tools.base import SystemTool
from dimensional_gateway.system_tools.list_modules import ListModulesTool
from dimensional_gateway.system_tools.load_blueprint import LoadBlueprintTool
from dimensional_gateway.system_tools.module_lifecycle import (
    BuildModuleTool,
    SetModuleRefTool,
    SetTransportTool,
    StartModuleTool,
    StopModuleTool,
)
from dimensional_gateway.system_tools.peek_stream import PeekStreamTool
from dimensional_gateway.system_tools.restart_module import RestartModuleTool
from dimensional_gateway.system_tools.stop_robot import StopRobotTool

SYSTEM_TOOLS: dict[str, type[SystemTool]] = {
    cls.name: cls
    for cls in [
        ListModulesTool,
        PeekStreamTool,
        LoadBlueprintTool,
        RestartModuleTool,
        StopRobotTool,
        BuildModuleTool,
        StartModuleTool,
        StopModuleTool,
        SetTransportTool,
        SetModuleRefTool,
    ]
}
