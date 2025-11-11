"""Core tools functionality for function calling."""
import pandas as pd

from services.battery.battery_service import BatteryService
from services.cpu.cpu_service import CPUService
from services.cpu.cpu_forecaster import CPUForecaster
from services.battery.battery_utility_calculator import BatteryUtilityCalculator
from services.test import BarService
from services.test import FooService


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
        bar_service = BarService()
        foo_service = FooService()
        forecaster = CPUForecaster()
        
        
        # Define tool functions that use our services
        def get_battery_status():
            """Get the current battery status."""
            return battery_service.get_battery_status()

        def get_cpu_status():
            """Get the current CPU status."""
            return cpu_service.get_cpu_status()
        
        def echo_test(value: int = 1):
            """Returns the received argument for debugging."""
            return foo_service.echo_test(value=value)

        def multi_argument_test(value: int, factor: float = 1.0):
            """
            Returns a dictionary with the received value and a computed result.
            
            Args:
                value (int): Main input value.
                factor (float, optional): Multiplier for the value. Defaults to 1.0.
            
            Returns:
                dict: Contains original value, factor, and computed result.
            """
            return bar_service.multi_argument_test(value=value, factor=factor)
        
                
        def get_cpu_forecast(prediction_length: int ):
            """Returns a CPU usage forecast from Chronos."""
            print(f"DEBUG: get_cpu_forecast received prediction_length={prediction_length}")
            result = forecaster.forecast_cpu(prediction_length=prediction_length)
            return result
        
        def battery_utility_calculator(storage_size_kwh: float):
            """Calculate the utility of a battery using sample energy data."""
            battery_calc_service = BatteryUtilityCalculator()
            print(f"DEBUG: battery_utility_calculator called with storage_size_kwh: {storage_size_kwh}")
            
            # Use sample/demo data for now
            sample_demand = pd.Series([10, 15, 20, 12, 8])
            sample_solar = pd.Series([5, 8, 12, 10, 3])
            sample_grid_prices = pd.Series([0.12, 0.15, 0.18, 0.14, 0.10])
            sample_eeg_prices = pd.Series([0.08, 0.08, 0.08, 0.08, 0.08])
            sample_community_prices = pd.Series([0.10, 0.11, 0.13, 0.12, 0.09])
            sample_wholesale_prices = pd.Series([0.06, 0.07, 0.09, 0.08, 0.05])
            
            return battery_calc_service.calculate(
                storage_size_kwh=storage_size_kwh,
                demand=sample_demand,
                solar_generation=sample_solar,
                grid_prices=sample_grid_prices,
                eeg_prices=sample_eeg_prices,
                community_prices=sample_community_prices,
                wholesale_prices=sample_wholesale_prices,
                solver="appsi_highs"
            )

        # Return list of tools with tracing applied
        return [
            tracer(get_battery_status),
            tracer(get_cpu_status),
            tracer(battery_utility_calculator),
            tracer(get_cpu_forecast),
            tracer(echo_test),
            tracer(multi_argument_test)
        ]