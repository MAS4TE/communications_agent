"""Core tools functionality for function calling."""

from datetime import datetime
from functools import wraps

from communication_agent.services.battery_service import BatteryService
from communication_agent.services.battery_utility_calculator import BatteryUtilityCalculator
from communication_agent.agent_state import shared_agent_state

import pytz
from datetime import datetime

def trace_tool(tool_fn):
    """Decorator to trace tool calls."""
    @wraps(tool_fn)
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
        """
        # === Services ===
        battery_service = BatteryService()
        buc_service = BatteryUtilityCalculator()
        agent_state = shared_agent_state

        # === Battery tools ===
        @tracer
        def get_battery_status():
            """Get the current battery status."""
            return battery_service.get_battery_status()

        @tracer
        def get_battery_utility():
            """Run the battery utility calculator."""
            return buc_service.calculate()

        # === Agent state tools ===
        @tracer
        def get_suggested_bid():
            """Return the current suggested bid stored in the agent state."""
            return agent_state.get_suggested_bid()

        @tracer
        def set_suggested_bid(price: float, volume: float):
            """Update the suggested bid with a new price and/or volume."""
            agent_state.set_suggested_bid(price=price, volume=volume)
            return {
                "status": "updated",
                "suggested_bid": agent_state.get_suggested_bid(),
            }
        
        @tracer
        def get_time():
            # Set the timezone to Netherlands
            nl_timezone = pytz.timezone("Europe/Amsterdam")
            # Get current datetime in NL
            current_time_nl = datetime.now(nl_timezone)
            print(current_time_nl.strftime("%Y-%m-%d %H:%M:%S"))
            return current_time_nl.strftime("%Y-%m-%d %H:%M:%S")


        # Return all tools in a list
        # return [
        #     get_battery_status,
        #     get_battery_utility,
        #     get_suggested_bid,
        #     set_suggested_bid,
        # ]
        return [
            get_suggested_bid
        ]