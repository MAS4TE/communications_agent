"""Core tools functionality for function calling."""

from datetime import datetime
from functools import wraps

from fastapi_app.services.battery_service import BatteryService

def trace_tool(tool_fn):
    """Decorator to trace tool calls."""
    @wraps(tool_fn)  # preserves __name__, __doc__, etc.
    def wrapper(*args, **kwargs):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{timestamp}] TOOL {tool_fn.__name__} called with args={args}, kwargs={kwargs}")
        return tool_fn(*args, **kwargs)
    return wrapper

class Tools:
    """Registry and management of available tools for function calling."""
    
    @staticmethod
    def get_tools(tracer=trace_tool):
        """
        Get all available tools with optional tracing.
        
        Args:
            tracer: Decorator function to apply to each tool
            
        Returns:
            list: List of tool functions
        """
        # Create battery service for tools to use
        battery_service = BatteryService()
        
        # Define tool functions that use our services
        def get_battery_status():
            """Get the current battery status."""
            return battery_service.get_battery_status()
            
        # Return list of tools with tracing applied
        return [
            tracer(get_battery_status),
        ]