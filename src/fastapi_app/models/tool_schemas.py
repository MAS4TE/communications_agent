"""Tool schemas for function calling with OpenAI."""

tool_schemas = [
    {
        "name": "get_battery_status",
        "description": "Returns the current battery level of the device as a percentage.",
        "parameters": {}  # no inputs needed for now
    }
]