from datetime import datetime
from functools import wraps
from inspect import signature
from typing import Callable

from core.llm.tools.registry import tool_registry  # singleton instance


def trace_tool(tool_fn):
    """Decorator to trace tool calls."""
    @wraps(tool_fn)  # preserves __name__, __doc__, etc.
    def wrapper(*args, **kwargs):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{timestamp}] TOOL {tool_fn.__name__} called with args={args}, kwargs={kwargs}")
        return tool_fn(*args, **kwargs)
    
    wrapper.__signature__ = signature(tool_fn)
    return wrapper

def tool(schema: dict):
    """Decorator to register a tool with its schema."""
    def wrapper(fn: Callable):
        tool_registry.register_tool(fn, schema)
        return fn
    return wrapper