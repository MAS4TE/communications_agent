# core/llm/tools/echo_tool.py
from core.llm.tools.decorators import tool, trace_tool
from core.domain.test import FooService

foo_service = FooService()

@tool(
    schema={
        "type": "function",
        "function": {
            "name": "echo_test",
            "description": "Echoes back the provided integer value (for debugging argument passing).",
            "parameters": {
                "type": "object",
                "properties": {
                    "value": {
                        "type": "number",
                        "description": "Any numeric value to echo back"
                    }
                },
                "required": ["value"]
            }
        }
    },
)
@trace_tool
def echo_test(value: int):
    """Tool wrapper to echo the provided integer value."""
    return foo_service.echo_test(value=value)
