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

        df = calculate_multiple_storage_worth(
            baseline_storage=baseline,
            storages_to_calculate=[candidate],
            **shared_kwargs,
        )

        single_worth = float(df.loc[df["id"] == candidate.id, "worth"].values[0])

        curve = calculate_bidding_curve(volumes_worth=df, buy_or_sell_side="buyer")

        return {
            "single_worth": single_worth,
            "multi_worth": df.to_dict(),
            "bidding_curve": curve.to_dict(),
        }