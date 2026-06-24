# core/llm/tools/battery_utility_tool.py
import pandas as pd
from core.llm.tools.decorators import tool, trace_tool
from core.domain.battery_utility_logic import BatteryUtilityCalculator
from battery_utility_calculator import Storage

import time
import traceback


def _ensure_series(data, index):
    """
    Converts a plain list or array to a pd.Series with the given index.
    If data is already a pd.Series, returns it unchanged.
    This is needed because the LLM passes arrays, but the optimizer expects pd.Series.
    """
    if isinstance(data, pd.Series):
        return data
    return pd.Series(data, index=index)


@tool(
    schema={
        "type": "function",
        "function": {
            "name": "battery_utility_calculator",
            "description": (
                "Calculate the worth (EUR value) of a candidate battery storage compared "
                "to a baseline, given energy timeseries and price data. "
                "Worth = how much better off the prosumer is with the candidate vs baseline. "
                "For sellers: baseline is their full battery, candidate is what they keep "
                "after renting out N kWh — worth is their opportunity cost (minimum ask price). "
                "For buyers: baseline is 0 kWh, candidate is N kWh of virtual storage — "
                "worth is their cost saving (maximum bid price). "
                "Use goal='max_cashflow' to minimize electricity costs, or "
                "'max_green_energy' to maximize solar self-consumption."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "storage_size_kwh": {
                        "type": "number",
                        "description": (
                            "Size of the candidate storage in kWh. "
                            "Sellers: full_battery_kwh - N (what they keep after renting out N kWh). "
                            "Buyers: N (the virtual storage capacity they are purchasing)."
                        )
                    },
                    "baseline_storage_kwh": {
                        "type": "number",
                        "description": (
                            "Size of the baseline storage in kWh — the reference point for worth. "
                            "Sellers: their full battery size (reference = keeping everything). "
                            "Buyers: 0 (reference = no storage at all)."
                        ),
                        "default": 0
                    },
                    "demand_series": {
                        "type": "array",
                        "items": {"type": "number"},
                        "description": "Demand timeseries in kWh per hour."
                    },
                    "solar_series": {
                        "type": "array",
                        "items": {"type": "number"},
                        "description": "Solar generation timeseries in kWh per hour."
                    },
                    "grid_prices": {
                        "type": "array",
                        "items": {"type": "number"},
                        "description": "Supplier/grid electricity prices in EUR/kWh."
                    },
                    "eeg_prices": {
                        "type": "array",
                        "items": {"type": "number"},
                        "description": "EEG feed-in prices in EUR/kWh."
                    },
                    "community_prices": {
                        "type": "array",
                        "items": {"type": "number"},
                        "description": "Community market prices in EUR/kWh."
                    },
                    "wholesale_prices": {
                        "type": "array",
                        "items": {"type": "number"},
                        "description": "Wholesale market prices in EUR/kWh."
                    },
                    "solver": {
                        "type": "string",
                        "description": "Solver to use for optimization. Defaults to 'appsi_highs'.",
                        "default": "appsi_highs"
                    },
                    "goal": {
                        "type": "string",
                        "enum": ["max_cashflow", "max_green_energy"],
                        "description": (
                            "'max_cashflow': minimize total electricity cost. "
                            "'max_green_energy': maximize solar self-consumption, "
                            "even if that costs more money."
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
    baseline_storage: Storage,
    storages_to_calculate: list[Storage],
    demand_series=None,
    solar_series=None,
    grid_prices=None,
    eeg_prices=None,
    community_prices=None,
    wholesale_prices=None,
    my_location: str = "aachen",
    is_rented_storage: bool = False,
    trading_scope: str = "All",
    solver: str = "appsi_highs",
    goal: str = "max_cashflow",
    return_charge_timeseries: bool = False,
) -> dict:

    battery_calc_service = BatteryUtilityCalculator()

    n = len(demand_series) if demand_series is not None else 5
    index = pd.date_range("2024-01-01", periods=n, freq="h")
    default_index = pd.date_range("2024-01-01", periods=5, freq="h")

    demand    = _ensure_series(demand_series,    index) if demand_series    is not None else pd.Series([10, 15, 20, 12, 8],             index=default_index)
    solar     = _ensure_series(solar_series,     index) if solar_series     is not None else pd.Series([5, 8, 12, 10, 3],               index=default_index)
    grid      = _ensure_series(grid_prices,      index) if grid_prices      is not None else pd.Series([0.12, 0.15, 0.18, 0.14, 0.10], index=default_index)
    eeg       = _ensure_series(eeg_prices,       index) if eeg_prices       is not None else pd.Series([0.08, 0.08, 0.08, 0.08, 0.08], index=default_index)
    community = _ensure_series(community_prices, index) if community_prices is not None else pd.Series([0.10, 0.11, 0.13, 0.12, 0.09], index=default_index)
    wholesale = _ensure_series(wholesale_prices, index) if wholesale_prices is not None else pd.Series([0.06, 0.07, 0.09, 0.08, 0.05], index=default_index)

    start_time = time.time()
    try:
        result = battery_calc_service.calculate(
            baseline_storage=baseline_storage,
            storages_to_calculate=storages_to_calculate,
            demand=demand,
            solar_generation=solar,
            grid_prices=grid,
            eeg_prices=eeg,
            community_prices=community,
            wholesale_prices=wholesale,
            my_location=my_location,
            is_rented_storage=is_rented_storage,
            trading_scope=trading_scope,
            solver=solver,
            goal=goal,
            return_charge_timeseries=return_charge_timeseries,
        )
    except Exception as e:
        print("Exception in battery_calc_service.calculate!")
        traceback.print_exc()
        raise

    print(f"  [BUC tool] done")
    return result