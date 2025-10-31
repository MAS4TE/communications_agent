"""Tool schemas for function calling with OpenAI."""

tool_schemas = [
    {
        "name": "get_battery_status",
        "description": "Returns the current battery level of the device as a percentage.",
        "parameters": {}  # no inputs needed
    },
    {
        "name": "get_cpu_status",
        "description": "Returns the current CPU usage percentage and core count.",
        "parameters": {}
    },
    {
        "name": "get_cpu_forecast",
        "description": "Returns the average CPU usage percent from the log as a forecast.",
        "parameters": {}
    }
]