# core/domain/battery_utility_logic.py
import pandas as pd
from battery_utility_calculator import (
    Storage,
    calculate_multiple_storage_worth,
    calculate_multiple_storage_worth_by_location,
)

KNOWN_SELLER_LOCATIONS = ["aachen", "juelich", "heerlen", "liege"]

LOCATION_COUNTRY = {
    "aachen":  "germany",
    "juelich": "germany",
    "heerlen": "netherlands",
    "liege":   "belgium",
}

def _resolve_locations(trading_scope: str, my_location: str, all_locations: list[str]) -> list[str]:
    if trading_scope == "Community":
        return [my_location]
    if trading_scope == "Country":
        my_country = LOCATION_COUNTRY.get(my_location.lower())
        return [loc for loc in all_locations if LOCATION_COUNTRY.get(loc) == my_country]
    # "All"
    return all_locations


class BatteryUtilityCalculator:

    def calculate(
        self,
        baseline_storage: Storage,
        storages_to_calculate: list[Storage],
        demand: pd.Series,
        solar_generation: pd.Series,
        grid_prices: pd.Series,
        eeg_prices: pd.Series,
        community_prices: pd.Series,
        wholesale_prices: pd.Series,
        my_location: str = "aachen",
        is_rented_storage: bool = False,
        seller_locations: list[str] = KNOWN_SELLER_LOCATIONS,
        trading_scope: str = "All",
        solver: str = "appsi_highs",
        goal: str = "max_cashflow",
        return_charge_timeseries: bool = False,
    ) -> dict:

        if is_rented_storage:
            locations_to_calculate = _resolve_locations(trading_scope, my_location.lower(), seller_locations)
            community_market_prices = {loc: community_prices for loc in locations_to_calculate}

            result_by_location = calculate_multiple_storage_worth_by_location(
                baseline_storage=baseline_storage,
                storages_to_calculate=storages_to_calculate,
                locations_to_calculate=locations_to_calculate,
                demand=demand,
                solar_generation=solar_generation,
                supplier_prices=grid_prices,
                eeg_prices=eeg_prices,
                community_market_prices=community_market_prices,
                wholesale_market_prices=wholesale_prices,
                my_location=my_location,
                solver=solver,
                goal=goal,
                return_charge_timeseries=return_charge_timeseries,
            )

            result_without_location = calculate_multiple_storage_worth(
                baseline_storage=baseline_storage,
                storages_to_calculate=storages_to_calculate,
                demand=demand,
                solar_generation=solar_generation,
                supplier_prices=grid_prices,
                eeg_prices=eeg_prices,
                community_market_prices={my_location: community_prices},
                wholesale_market_prices=wholesale_prices,
                my_location=my_location,
                is_rented_storage=True,
                solver=solver,
                goal=goal,
                return_charge_timeseries=False,
            )

            print("=== BUYER: BY LOCATION ===")
            print(result_by_location if isinstance(result_by_location, pd.DataFrame) else result_by_location["results_df"])
            print("=== BUYER: WITHOUT LOCATION ===")
            print(result_without_location if isinstance(result_without_location, pd.DataFrame) else result_without_location["results_df"])

            result = result_by_location
            if isinstance(result, pd.DataFrame):
                result = {"results_df": result}

        else:
            result_with_location = calculate_multiple_storage_worth_by_location(
                baseline_storage=baseline_storage,
                storages_to_calculate=storages_to_calculate,
                locations_to_calculate=[my_location],
                demand=demand,
                solar_generation=solar_generation,
                supplier_prices=grid_prices,
                eeg_prices=eeg_prices,
                community_market_prices={my_location: community_prices},
                wholesale_market_prices=wholesale_prices,
                my_location=my_location,
                solver=solver,
                goal=goal,
                return_charge_timeseries=False,
            )

            result = calculate_multiple_storage_worth(
                baseline_storage=baseline_storage,
                storages_to_calculate=storages_to_calculate,
                demand=demand,
                solar_generation=solar_generation,
                supplier_prices=grid_prices,
                eeg_prices=eeg_prices,
                community_market_prices={my_location: community_prices},
                wholesale_market_prices=wholesale_prices,
                my_location=my_location,
                is_rented_storage=False,
                solver=solver,
                goal=goal,
                return_charge_timeseries=return_charge_timeseries,
            )

            print("=== SELLER: BY LOCATION ===")
            print(result_with_location if isinstance(result_with_location, pd.DataFrame) else result_with_location["results_df"])
            print("=== SELLER: WITHOUT LOCATION ===")
            print(result if isinstance(result, pd.DataFrame) else result["results_df"])

            if isinstance(result, pd.DataFrame):
                result = {"results_df": result}

        return result