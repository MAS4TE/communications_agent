# core/llm/tools/multi_argument_tool.py
from core.llm.tools.decorators import tool, trace_tool
from core.domain.test import BarService

bar_service = BarService()
@tool(
    schema={
        "type": "function",
        "function": {
            "name": "multi_argument_test",
            "description": "Returns a dictionary with the received value and a computed result (for debugging multiple arguments).",
            "parameters": {
                "type": "object",
                "properties": {
                    "value": {
                        "type": "integer",
                        "description": "Main input value"
                    },
                    "factor": {
                        "type": "number",
                        "description": "Multiplier for the value",
                        "default": 1.0
                    }
                },
                "required": ["value"]
            }
        }
    }
)
@trace_tool
def multi_argument_test(value: int, factor: float = 1.0):
    """Tool wrapper to test multiple arguments."""
    return bar_service.multi_argument_test(value=value, factor=factor)
