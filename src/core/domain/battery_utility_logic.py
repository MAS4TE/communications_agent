# core/domain/battery_utility_logic.py
import pandas as pd
from battery_utility_calculator import (
    Storage,
    calculate_storage_worth,
)


class BatteryUtilityCalculator:
    """
    Wrapper around the battery_utility_calculator library for single-candidate worth calculation.

    Computes the 'worth' of a candidate storage configuration compared to a baseline,
    where worth = cost(baseline) - cost(candidate), i.e. how much better off the
    prosumer is with the candidate storage vs the baseline.

    This class is intentionally kept simple — it handles one baseline vs one candidate.
    The step function is responsible for:
      - deciding what the baseline and candidate should be (seller vs buyer logic)
      - looping over volumes
      - assembling the bidding curve from the collected worth values
    """

    def calculate(
        self,
        storage_size_kwh: float,
        baseline_storage_kwh: float,
        demand: pd.Series,
        solar_generation: pd.Series,
        grid_prices: pd.Series,
        eeg_prices: pd.Series,
        community_prices: pd.Series,
        wholesale_prices: pd.Series,
        solver: str = "appsi_highs",
        goal: str = "max_cashflow",
        return_charge_timeseries: bool = False,
    ) -> dict:
        """
        Calculate the worth of a candidate storage vs a baseline storage.

        The worth represents different things depending on the role of the prosumer:

          Seller: baseline = full battery (self-consuming only)
                  candidate = full battery minus N kWh being rented out
                  → worth = opportunity cost of renting out N kWh
                  → interpretation: minimum price the seller should accept

          Buyer:  baseline = 0 kWh (no storage at all)
                  candidate = N kWh of virtual storage being purchased
                  → worth = energy cost savings from having N kWh available
                  → interpretation: maximum price the buyer should be willing to pay

        Args:
            storage_size_kwh (float): Size of the candidate storage in kWh.
                For sellers: full_battery - N (what they keep after renting out N kWh).
                For buyers: N (the virtual storage they are buying).
            baseline_storage_kwh (float): Size of the baseline storage in kWh.
                For sellers: their full battery size (reference = keeping everything).
                For buyers: 0 (reference = no storage).
            demand (pd.Series): Demand timeseries in kWh per hour.
            solar_generation (pd.Series): Solar generation timeseries in kWh per hour.
            grid_prices (pd.Series): Supplier/grid electricity prices in EUR/kWh.
            eeg_prices (pd.Series): EEG feed-in prices in EUR/kWh.
            community_prices (pd.Series): Community market prices in EUR/kWh.
            wholesale_prices (pd.Series): Wholesale market prices in EUR/kWh.
            solver (str): Solver to use for the optimization. Defaults to 'appsi_highs'.
            goal (str): Optimization goal.
                'max_cashflow'    → minimize total electricity cost.
                'max_green_energy' → maximize solar self-consumption.
            return_charge_timeseries (bool): If True, includes the candidate storage's
                charge/discharge timeseries in the output. Used downstream for MQTT
                battery scheduling. Defaults to False.

        Returns:
            dict with keys:
                'worth' (float): EUR value of candidate vs baseline. Positive means
                    the candidate is better (cheaper for buyers, lower opportunity
                    cost for sellers).
                'storage_to_calc_charge_ts' (pd.DataFrame): Only present when
                    return_charge_timeseries=True. Charge timeseries of the candidate
                    storage, used for battery scheduling via MQTT.
        """

        # Storage constructor: Storage(id, c_rate, volume, efficiency)
        # id=0 for baseline, id=1 for candidate — these are arbitrary internal identifiers
        baseline  = Storage(0, 1, baseline_storage_kwh, 1)
        candidate = Storage(1, 1, storage_size_kwh, 1)

        result = calculate_storage_worth(
            baseline_storage=baseline,
            storage_to_calculate=candidate,
            demand=demand,
            solar_generation=solar_generation,
            supplier_prices=grid_prices,
            eeg_prices=eeg_prices,
            community_market_prices=community_prices,
            wholesale_market_prices=wholesale_prices,
            solver=solver,
            return_charge_timeseries=return_charge_timeseries,
        )

        # calculate_storage_worth returns a dict when return_charge_timeseries=True,
        # otherwise a plain float
        if return_charge_timeseries:
            worth     = result["worth"]
            charge_ts = result["storage_to_calc_charge_ts"]
        else:
            worth     = result
            charge_ts = None

        out = {"worth": worth}
        if return_charge_timeseries:
            out["storage_to_calc_charge_ts"] = charge_ts

        return out