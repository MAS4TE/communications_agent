from typing import Dict, Any

import pandas as pd

from core.domain.storage import Storage

def calculate_storage_worth(
    baseline_storage: Storage,
    storage_to_calculate: Storage,
    demand: pd.Series,
    solar_generation: pd.Series,
    grid_prices: pd.Series,
    eeg_prices: pd.Series,
    community_market_prices: pd.Series, 
    wholesale_market_prices : pd.Series,       
    solver="appsi_highs"
    ) -> float:
    """Mock calculate_storage_worth function - returns 1 or 0"""

    storage_worth = 1 if storage_to_calculate.volume > 0 else 0
    return storage_worth

def calculate_bidding_curve(
    volumes_worth: pd.DataFrame, 
    buy_or_sell_side="seller"
    ) -> pd.DataFrame:
    """Mock calculate_bidding_curve function"""
    return [{"volume": 0, "price": 1}, {"volume": 10, "price": 0}]

class BatteryUtilityCalculator:
    """Battery Utility Calculator service."""
    def calculate(
            self,
            storage_size_kwh: float,
            demand: pd.Series,
            solar_generation: pd.Series,
            grid_prices: pd.Series,
            eeg_prices: pd.Series,
            community_prices: pd.Series,
            wholesale_prices: pd.Series, 
            solver: str="appsi_highs"
        ) -> Dict[str, Any]:
            
            # baseline storage: empty
            baseline_storage = Storage(
                id=0, 
                c_rate=1, 
                volume=0, 
                charge_efficiency=1,
                discharge_efficiency=1
                )
            # optimized storage: full requested size
            optimized_storage = Storage(
                id=0, 
                c_rate=1, 
                volume=storage_size_kwh, 
                charge_efficiency=0.95,
                discharge_efficiency=0.95
            )

            # calculate baseline and optimized costs
            baseline_cost = calculate_storage_worth(
                baseline_storage=baseline_storage,
                storage_to_calculate=baseline_storage,
                eeg_prices=eeg_prices,
                wholesale_market_prices=wholesale_prices,
                community_market_prices=community_prices,
                grid_prices=grid_prices,
                solar_generation=solar_generation,
                demand=demand,
                solver=solver
            )

            optimized_cost = calculate_storage_worth(
                baseline_storage=baseline_storage,
                storage_to_calculate=optimized_storage,
                eeg_prices=eeg_prices,
                wholesale_market_prices=wholesale_prices,
                community_market_prices=community_prices,
                grid_prices=grid_prices,
                solar_generation=solar_generation,
                demand=demand,
                solver=solver
            )

            # compute cost savings
            cost_savings = baseline_cost - optimized_cost

            # prepare dataframe for bidding curve
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