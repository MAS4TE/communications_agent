# core/llm/tools/cpu_tools.py
from core.llm.tools.decorators import tool, trace_tool
from core.domain.cpu_logic import get_cpu_metrics


@tool(
    schema={
        "name": "get_cpu_status",
        "description": "Returns the current CPU usage percentage and core count.",
        "parameters": {}
    }
)
@trace_tool
def get_cpu_status():
    """Tool wrapper for getting CPU status."""
    return get_cpu_metrics()
