# core/llm/tools/battery_utility_tool.py
import pandas as pd
from core.llm.tools.decorators import tool, trace_tool
from core.domain.battery_utility_logic import BatteryUtilityCalculator

import time
import traceback


def _ensure_series(data, index):
    if isinstance(data, pd.Series):
        return data
    return pd.Series(data, index=index)


@tool(
    schema={
        "type": "function",
        "function": {
            "name": "battery_utility_calculator",
            "description": (
                "Calculate the utility of a battery given its size and time series data. "
                "Returns baseline cost, optimized cost, cost savings, and a bidding curve. "
                "Use goal='max_cashflow' to minimize electricity costs, or "
                "goal='max_green_energy' to maximize solar self-consumption regardless of cost."
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
                    },
                    "goal": {
                        "type": "string",
                        "enum": ["max_cashflow", "max_green_energy"],
                        "description": (
                            "What to optimize for. 'max_cashflow' minimizes total electricity cost. "
                            "'max_green_energy' maximizes how much of the user's own solar power is "
                            "consumed directly, even if that costs more money."
                        ),
                        "default": "max_cashflow"
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
    demand_series=None,
    solar_series=None,
    grid_prices=None,
    eeg_prices=None,
    community_prices=None,
    wholesale_prices=None,
    solver: str = "appsi_highs",
    goal: str = "max_cashflow",
    return_charge_timeseries: bool = False,
):
    """
    Calculate the utility of a battery using sample or provided energy data.
    Returns baseline cost, optimized cost, cost savings, and a bidding curve.
    """
    battery_calc_service = BatteryUtilityCalculator()

    print('in BUC tool, storage size:', storage_size_kwh, '| goal:', goal)

    n = len(demand_series) if demand_series is not None else 5
    index = pd.date_range("2024-01-01", periods=n, freq="h")
    default_index = pd.date_range("2024-01-01", periods=5, freq="h")

    demand    = _ensure_series(demand_series,    index) if demand_series    is not None else pd.Series([10, 15, 20, 12, 8],              index=default_index)
    solar     = _ensure_series(solar_series,     index) if solar_series     is not None else pd.Series([5, 8, 12, 10, 3],                index=default_index)
    grid      = _ensure_series(grid_prices,      index) if grid_prices      is not None else pd.Series([0.12, 0.15, 0.18, 0.14, 0.10],  index=default_index)
    eeg       = _ensure_series(eeg_prices,       index) if eeg_prices       is not None else pd.Series([0.08, 0.08, 0.08, 0.08, 0.08],  index=default_index)
    community = _ensure_series(community_prices, index) if community_prices is not None else pd.Series([0.10, 0.11, 0.13, 0.12, 0.09],  index=default_index)
    wholesale = _ensure_series(wholesale_prices, index) if wholesale_prices is not None else pd.Series([0.06, 0.07, 0.09, 0.08, 0.05],  index=default_index)

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
            solver=solver,
            goal=goal,
            return_charge_timeseries=return_charge_timeseries,
        )
    except Exception as e:
        print("Exception in battery_calc_service.calculate!")
        traceback.print_exc()
        raise

    end_time = time.time()
    print(f"battery_calc_service.calculate finished in {end_time - start_time:.2f} seconds")

    return result