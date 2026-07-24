"""The Battery Utility Calculator (BUC), wrapped for our use.

``battery_utility_calculator`` is an external pip package that does the heavy
optimisation: given forecasts and prices, it works out how much a given amount
of storage is *worth* to this prosumer, and turns a range of storage sizes into
a bidding curve (volume + the marginal price per kWh).

This module is a thin, readable layer on top of that package:

  - ``storage_worth(...)``   run the optimiser for buyer or seller
  - ``bidding_curve(...)``   turn the per-volume worth into a bidding curve

The buyer/seller distinction matters:
  - Seller: owns a battery, rents part of it out. Worth is their opportunity
    cost (the minimum price they'll accept).
  - Buyer: owns no battery, rents virtual storage from the community. Worth is
    their cost saving (the maximum price they'll pay). Buyers also care *where*
    the storage is, so they use the by-location optimiser.
"""
import pandas as pd
from battery_utility_calculator import (
    Storage,
    calculate_bidding_curve,
    calculate_multiple_storage_worth,
    calculate_multiple_storage_worth_by_location,
)
from config import SELLER_LOCATIONS, LOCATION_COUNTRY


__all__ = ["Storage", "storage_worth", "bidding_curve"]

# Where seller batteries can physically live, and which country each is in.
# SELLER_LOCATIONS = ["aachen", "juelich", "heerlen", "liege"]
# LOCATION_COUNTRY = {
#     "aachen": "germany",
#     "juelich": "germany",
#     "heerlen": "netherlands",
#     "liege": "belgium",
# }


def _locations_in_scope(trading_scope: str, my_location: str) -> list[str]:
    """Which seller locations a buyer may trade with, given their scope setting."""
    if trading_scope == "Community":
        return [my_location]
    if trading_scope == "Country":
        my_country = LOCATION_COUNTRY.get(my_location)
        return [loc for loc in SELLER_LOCATIONS if LOCATION_COUNTRY.get(loc) == my_country]
    return SELLER_LOCATIONS                      # "All"


def storage_worth(
    *,
    baseline_storage: Storage,
    storages: list[Storage],
    demand: pd.Series,
    solar: pd.Series,
    grid_prices: pd.Series,
    eeg_prices: pd.Series,
    community_prices: pd.Series,
    wholesale_prices: pd.Series,
    my_location: str,
    is_buyer: bool,
    trading_scope: str = "All",
    goal: str = "max_cashflow",
    return_charge_timeseries: bool = False,
    solver: str = "appsi_highs",
) -> dict:
    """Run the optimiser and return a dict with at least ``results_df``.

    ``results_df`` has one row per candidate storage with its ``worth``; when
    ``return_charge_timeseries`` is set, the result also carries the per-storage
    charge schedules under ``storages_to_calc_charge_ts``.
    """
    my_location = my_location.lower()

    if is_buyer:
        locations = _locations_in_scope(trading_scope, my_location)
        result = calculate_multiple_storage_worth_by_location(
            baseline_storage=baseline_storage,
            storages_to_calculate=storages,
            locations_to_calculate=locations,
            demand=demand,
            solar_generation=solar,
            supplier_prices=grid_prices,
            eeg_prices=eeg_prices,
            community_market_prices={loc: community_prices for loc in locations},
            wholesale_market_prices=wholesale_prices,
            my_location=my_location,
            solver=solver,
            goal=goal,
            return_charge_timeseries=return_charge_timeseries,
        )
    else:
        result = calculate_multiple_storage_worth(
            baseline_storage=baseline_storage,
            storages_to_calculate=storages,
            demand=demand,
            solar_generation=solar,
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

    if isinstance(result, pd.DataFrame):
        result = {"results_df": result}
    return result


def bidding_curve(results_df: pd.DataFrame, *, is_buyer: bool, max_tradeable: int | None = None) -> pd.DataFrame:
    """Turn per-volume worth into a bidding curve (volume + marginal price).

    For sellers we also cap the curve at the volume they're willing to rent out.
    """
    side = "buyer" if is_buyer else "seller"
    columns = ["volume", "worth"]
    if "location" in results_df.columns:
        columns.append("location")

    curve = calculate_bidding_curve(volumes_worth=results_df[columns], buy_or_sell_side=side)
    if not is_buyer and max_tradeable is not None:
        curve = curve.head(max_tradeable)
    return curve
