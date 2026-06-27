"""Forecasting via the Chronos service.

The bidding pipeline needs to know what the next trading window looks like:
how much electricity the household will demand, how much solar it will
generate, and what the various energy prices will be. We get those forecasts
from a separate Chronos server (see config.CHRONOS_URL).

This module does one thing: take a CSV of historical values and a target
window, ask Chronos to predict it, and return the prediction as a pandas
Series indexed by 15-minute timestamps.
"""
import pandas as pd
import requests

from config import CHRONOS_URL, CHRONOS_TIMEOUT


def chronos_forecast(
    csv_path: str,
    start,
    end,
    value_col: str,
    history_days: int = 1,
    timestamp_col: str = "datetime",
) -> pd.Series:
    """Forecast one column of a CSV over the window [start, end).

    Args:
        csv_path:     path to a CSV with a timestamp column and ``value_col``.
        start, end:   the trading window to forecast (datetime-like).
        value_col:    which column to forecast (e.g. "load_kw", "solar_kw").
        history_days: how much history before ``start`` to feed Chronos.

    Returns:
        A Series of predicted values, indexed by 15-minute timestamps starting
        at ``start``.
    """
    start = pd.to_datetime(start, utc=True)
    end = pd.to_datetime(end, utc=True)

    df = (
        pd.read_csv(csv_path, parse_dates=[timestamp_col])
        .set_index(timestamp_col)
        .sort_index()
    )
    df.index = pd.to_datetime(df.index, utc=True)

    # The forecast horizon is the number of rows that fall inside the window.
    horizon = len(df.loc[start:end])
    if horizon <= 0:
        raise ValueError("Forecast window does not overlap the data")

    # History fed to the model: the days leading up to the window.
    history_df = df.loc[start - pd.Timedelta(days=history_days):start]
    history = [
        {"timestamp": ts.isoformat(), "value": float(v)}
        for ts, v in zip(history_df.index, history_df[value_col])
    ]

    response = requests.post(
        f"{CHRONOS_URL}/forecast",
        json={"history": history, "prediction_length": horizon},
        timeout=CHRONOS_TIMEOUT,
    )
    response.raise_for_status()
    median = response.json()["median"]

    timestamps = pd.date_range(start=start, periods=len(median), freq="15min")
    return pd.Series(median, index=timestamps.tz_localize(None))
