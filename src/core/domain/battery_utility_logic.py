# core/domain/battery_utility_logic.py
import pandas as pd
from battery_utility_calculator import (
    Storage,
    calculate_multiple_storage_worth,
    calculate_bidding_curve,
)


class BatteryUtilityCalculator:
    """Wrapper class around battery utility logic functions."""

    def calculate(
        self,
        storage_size_kwh: float,
        demand: pd.Series,
        solar_generation: pd.Series,
        grid_prices: pd.Series,
        eeg_prices: pd.Series,
        community_prices: pd.Series,
        wholesale_prices: pd.Series,
        solver: str = "appsi_highs",
        goal: str = "max_cashflow",
        return_charge_timeseries: bool = False, #for schedule
    ):
        baseline  = Storage(0, 1, 0, 1)
        candidate = Storage(1, 1, storage_size_kwh, 1)

        shared_kwargs = dict(
            eeg_prices=eeg_prices,
            wholesale_market_prices=wholesale_prices,
            community_market_prices=community_prices,
            supplier_prices=grid_prices,
            solar_generation=solar_generation,
            demand=demand,
            solver=solver,
            goal=goal,
        )

        # df = calculate_multiple_storage_worth(
        #     baseline_storage=baseline,
        #     storages_to_calculate=[candidate],
        #     return_charge_timeseries=return_charge_timeseries, # for schedule
        #     **shared_kwargs,
        # )

        result = calculate_multiple_storage_worth(
            baseline_storage=baseline,
            storages_to_calculate=[candidate],
            return_charge_timeseries=return_charge_timeseries,  # added
            **shared_kwargs,
        )

        # calculate_multiple_storage_worth returns a dict when return_charge_timeseries=True,
        # otherwise a plain DataFrame
        if return_charge_timeseries:
            df = result["results_df"]
            charge_ts = result["storages_to_calc_charge_ts"][candidate.id]
        else:
            df = result
            charge_ts = None

        single_worth = float(df.loc[df["id"] == candidate.id, "worth"].values[0])

        curve = calculate_bidding_curve(volumes_worth=df, buy_or_sell_side="buyer")

        # return {
        #     "single_worth": single_worth,
        #     "multi_worth": df.to_dict(),
        #     "bidding_curve": curve.to_dict(),
        # }
        out = {
            "single_worth": single_worth,
            "multi_worth": df.to_dict(),
            "bidding_curve": curve.to_dict(),
        }

        if return_charge_timeseries:
            out["storage_to_calc_charge_ts"] = charge_ts  # consistent key name

        return out