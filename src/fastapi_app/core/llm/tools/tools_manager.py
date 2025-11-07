import json
from typing import Callable, List, Optional

class ToolManager:
    """Handles tool registration, schemas, and invocation."""

    def __init__(self, tools: Optional[List[Callable]] = None, schemas: Optional[List[dict]] = None):
        """
        Initialize ToolManager with optional tools and schemas.
        If schemas are not provided, they will be generated from tool functions.
        """
        self.tools = tools or []
        if schemas and len(schemas) == len(tools):
            self.schemas = schemas
        else:
            self.schemas = self._build_schemas(self.tools)

    @staticmethod
    def _build_schemas(tools: List[Callable]) -> List[dict]:
        """Convert Python functions to OpenAI function schemas."""
        return [
            {
                "name": t.__name__,
                "description": t.__doc__ or f"Tool {t.__name__}",
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            }
            for t in tools
        ]

    def set_tools(self, tools: List[Callable]):
        self.tools = tools
        self.schemas = self._build_schemas(tools)

    def call_tool(self, name: str, args: dict) -> str:
        tool_fn = next((t for t in self.tools if t.__name__ == name), None)
        if not tool_fn:
            return f"Error: Tool '{name}' is not available."
        return str(tool_fn(**args))
