from datetime import datetime
from inspect import signature
from functools import wraps

def trace_tool(tool_fn):
    """Decorator to trace tool calls."""
    @wraps(tool_fn)  # preserves __name__, __doc__, etc.
    def wrapper(*args, **kwargs):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{timestamp}] TOOL {tool_fn.__name__} called with args={args}, kwargs={kwargs}")
        return tool_fn(*args, **kwargs)
    
    wrapper.__signature__ = signature(tool_fn)
    return wrapper