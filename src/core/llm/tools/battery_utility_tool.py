# core/llm/tools/battery_utility_tool.py
import pandas as pd
from core.llm.tools.decorators import tool, trace_tool
from core.domain.battery_utility_calculator import BatteryUtilityCalculator


@tool(
    schema={
        "type": "function",
        "function": {
            "name": "battery_utility_calculator",
            "description": (
                "Calculate the utility of a battery given its size and time series data. "
                "Returns baseline cost, optimized cost, cost savings, and a bidding curve."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "storage_size_kwh": {
                        "type": "number",
                        "description": "Size of the battery in kWh"
                    },
                    "demand_series": {
                        "type": "array",
                        "items": {"type": "number"},
                        "description": "Array of demand values"
                    },
                    "solar_series": {
                        "type": "array",
                        "items": {"type": "number"},
                        "description": "Array of solar generation values"
                    },
                    "grid_prices": {
                        "type": "array",
                        "items": {"type": "number"},
                        "description": "Array of grid prices"
                    },
                    "eeg_prices": {
                        "type": "array",
                        "items": {"type": "number"},
                        "description": "Array of EEG prices"
                    },
                    "community_prices": {
                        "type": "array",
                        "items": {"type": "number"},
                        "description": "Array of community market prices"
                    },
                    "wholesale_prices": {
                        "type": "array",
                        "items": {"type": "number"},
                        "description": "Array of wholesale market prices"
                    },
                    "solver": {
                        "type": "string",
                        "description": "Solver to use (default 'appsi_highs')",
                        "default": "appsi_highs"
                    }
                },
                "required": [
                    "storage_size_kwh",
                    "demand_series",
                    "solar_series",
                    "grid_prices",
                    "eeg_prices",
                    "community_prices",
                    "wholesale_prices"
                ]
            }
        }
    }
)
@trace_tool
def battery_utility_calculator(
    storage_size_kwh: float,
    demand_series: list[float] | None = None,
    solar_series: list[float] | None = None,
    grid_prices: list[float] | None = None,
    eeg_prices: list[float] | None = None,
    community_prices: list[float] | None = None,
    wholesale_prices: list[float] | None = None,
    solver: str = "appsi_highs"
):
    """
    Calculate the utility of a battery using sample or provided energy data.
    Returns baseline cost, optimized cost, cost savings, and a bidding curve.
    """
    battery_calc_service = BatteryUtilityCalculator()
    print(f"DEBUG: battery_utility_calculator called with storage_size_kwh={storage_size_kwh}")

    # If no arrays provided, use sample demo data
    demand = pd.Series(demand_series or [10, 15, 20, 12, 8])
    solar = pd.Series(solar_series or [5, 8, 12, 10, 3])
    grid = pd.Series(grid_prices or [0.12, 0.15, 0.18, 0.14, 0.10])
    eeg = pd.Series(eeg_prices or [0.08, 0.08, 0.08, 0.08, 0.08])
    community = pd.Series(community_prices or [0.10, 0.11, 0.13, 0.12, 0.09])
    wholesale = pd.Series(wholesale_prices or [0.06, 0.07, 0.09, 0.08, 0.05])

    result = battery_calc_service.calculate(
        storage_size_kwh=storage_size_kwh,
        demand=demand,
        solar_generation=solar,
        grid_prices=grid,
        eeg_prices=eeg,
        community_prices=community,
        wholesale_prices=wholesale,
        solver=solver
    )

    return result
