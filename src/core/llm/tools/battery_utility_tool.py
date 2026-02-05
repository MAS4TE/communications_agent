# core/llm/tools/battery_utility_tool.py
import pandas as pd
from core.llm.tools.decorators import tool, trace_tool
from core.domain.battery_utility_logic import BatteryUtilityCalculator

import time
import traceback


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
    # print(f"DEBUG: battery_utility_calculator called with storage_size_kwh={storage_size_kwh}")

    print('in BUC tool, storage size ', storage_size_kwh)

    # Convert optional lists to pandas Series with sample defaults if None
    # demand = pd.Series(demand_series or [10, 15, 20, 12, 8])
    # solar = pd.Series(solar_series or [5, 8, 12, 10, 3])
    # grid = pd.Series(grid_prices or [0.12, 0.15, 0.18, 0.14, 0.10])
    # eeg = pd.Series(eeg_prices or [0.08, 0.08, 0.08, 0.08, 0.08])
    # community = pd.Series(community_prices or [0.10, 0.11, 0.13, 0.12, 0.09])
    # wholesale = pd.Series(wholesale_prices or [0.06, 0.07, 0.09, 0.08, 0.05])

    demand = pd.Series(demand_series) if demand_series is not None else pd.Series([10, 15, 20, 12, 8])
    solar = pd.Series(solar_series) if solar_series is not None else pd.Series([5, 8, 12, 10, 3])
    grid = pd.Series(grid_prices) if grid_prices is not None else pd.Series([0.12, 0.15, 0.18, 0.14, 0.10])
    eeg = pd.Series(eeg_prices) if eeg_prices is not None else pd.Series([0.08, 0.08, 0.08, 0.08, 0.08])
    community = pd.Series(community_prices) if community_prices is not None else pd.Series([0.10, 0.11, 0.13, 0.12, 0.09])
    wholesale = pd.Series(wholesale_prices) if wholesale_prices is not None else pd.Series([0.06, 0.07, 0.09, 0.08, 0.05])


    # print('in BUC tool, demand ', demand)

    # result = battery_calc_service.calculate(
    #     storage_size_kwh=storage_size_kwh,
    #     demand=demand,
    #     solar_generation=solar,
    #     grid_prices=grid,
    #     eeg_prices=eeg,
    #     community_prices=community,
    #     wholesale_prices=wholesale,
    #     solver=solver
    # )

    print("About to call battery_calc_service.calculate(...)")

    start_time = time.time()

    try:
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
    except Exception as e:
        print("Exception in battery_calc_service.calculate!")
        traceback.print_exc()
        raise

    end_time = time.time()
    print(f"battery_calc_service.calculate finished in {end_time - start_time:.2f} seconds")


    return result