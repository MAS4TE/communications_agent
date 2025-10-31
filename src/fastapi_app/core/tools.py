"""Core tools functionality for function calling."""

from datetime import datetime
from functools import wraps

from fastapi_app.services.battery_service import BatteryService
from fastapi_app.services.cpu_service import CPUService
from fastapi_app.core.cpu_forecaster import CPUForecaster


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
        cpu_service = CPUService()
        
        # Define tool functions that use our services
        def get_battery_status():
            """Get the current battery status."""
            return battery_service.get_battery_status()

        def get_cpu_status():
            """Get the current CPU status."""
            return cpu_service.get_cpu_status()
                
        def get_cpu_forecast(prediction_length=1):
            """Returns a CPU usage forecast from Chronos."""
            forecaster = CPUForecaster()
            result = forecaster.forecast_cpu(prediction_length=prediction_length)
            return result

        # Return list of tools with tracing applied
        return [
            tracer(get_battery_status),
            tracer(get_cpu_status),
            tracer(get_cpu_forecast),
        ]