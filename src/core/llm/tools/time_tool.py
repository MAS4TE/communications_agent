from core.llm.tools.decorators import tool, trace_tool
from datetime import datetime

@tool(
    schema={
        "name": "get_current_time",
        "description": "Returns the current date and time in ISO format",
        "parameters": {}
    }
)
@trace_tool
def get_current_time():
    """Tool that returns the current date and time"""
    return {"current_time": datetime.now().isoformat()}
