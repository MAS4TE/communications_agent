# core/llm/tools/battery_tools.py
from core.llm.tools.decorators import tool, trace_tool
from core.domain.battery_logic import get_battery_metrics


@tool(
    schema={
        "name": "get_battery_status",
        "description": "Returns the current battery level of the device as a percentage",
        "parameters": {}
    }
)
@trace_tool
def get_battery_status():
    """Tool wrapper for BatteryService.get_battery_status"""
    return get_battery_metrics()

