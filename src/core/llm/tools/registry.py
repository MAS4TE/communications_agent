# core/llm/tools/registry.py
from typing import Callable, List, Dict

class ToolRegistry:
    """Central registry for tools and their schemas."""

    def __init__(self):
        self._tools: List[Callable] = []
        self._schemas: List[Dict] = []

    def register_tool(self, tool_fn: Callable, schema: Dict):
        """Register a tool function and its schema."""
        self._tools.append(tool_fn)
        self._schemas.append(schema)

    @property
    def tools(self) -> List[Callable]:
        return self._tools

    @property
    def schemas(self) -> List[Dict]:
        return self._schemas
    
# Singleton instance used by all tool modules
tool_registry = ToolRegistry()