"""
Battery Utility Calculator (BUC) service wrapper.
Compatible with the NOWUM battery-utility-calculator library.
"""

import pandas as pd
from battery_utility_calculator.battery_utility_calculator import (
    Storage,
    calculate_storage_worth,
    calculate_bidding_curve,
)

class BatteryUtilityCalculator:
    """
    Wraps NOWUM BUC functions for easy use.
    """

    def calculate(
        self,
        storage_size_kwh: float,
        demand: pd.Series,
        solar_generation: pd.Series,
        grid_prices: pd.Series,
        eeg_prices: pd.Series,
        community_prices: pd.Series,
        wholesale_prices: pd.Series, 
        solver: str="appsi_highs" #default solver changed for Bea
    ):
        # baseline storage: empty
        baseline_storage = Storage(id=0, c_rate=1, volume=0, efficiency=1)
        # optimized storage: full requested size
        optimized_storage = Storage(id=0, c_rate=1, volume=storage_size_kwh, efficiency=0.95)

        # calculate baseline and optimized costs
        baseline_cost = calculate_storage_worth(
            baseline_storage,
            baseline_storage,  # baseline compared to itself
            demand,
            solar_generation,
            grid_prices,
            eeg_prices,
            community_prices,
            wholesale_prices, 
            solver=solver
        )

        optimized_cost = calculate_storage_worth(
            baseline_storage,
            optimized_storage,
            demand,
            solar_generation,
            grid_prices,
            eeg_prices,
            community_prices,
            wholesale_prices, 
            solver=solver
        )

        # compute cost savings
        cost_savings = baseline_cost - optimized_cost

        # prepare dataframe for bidding curve
        import pandas as pd
        volumes_worth_df = pd.DataFrame({
            "volume": [0, optimized_storage.volume],
            "worth": [baseline_cost, optimized_cost]
        })

        bidding_curve = calculate_bidding_curve(
            volumes_worth_df,
            buy_or_sell_side="seller"
        )

        return {
            "storage_size_kwh": storage_size_kwh,
            "baseline_cost": baseline_cost,
            "optimized_cost": optimized_cost,
            "cost_savings": cost_savings,
            "bidding_curve": bidding_curve
        }
