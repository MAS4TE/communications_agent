"""Core tools functionality for function calling."""
from services.battery.battery_service import BatteryService
from services.cpu.cpu_service import CPUService
from services.cpu.cpu_forecaster import CPUForecaster

from .llm.tools.decorators import trace_tool


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