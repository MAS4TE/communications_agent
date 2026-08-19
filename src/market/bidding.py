"""The bidding pipeline — runs when the market opens.

Read this file top to bottom: it is the complete answer to "what does the agent
do when the market opens?"

    preferences -> profile (buyer or seller?) -> trading window
        -> forecast demand, solar and prices
        -> (buyers) ask the LLM how far to search
        -> Battery Utility Calculator -> bidding curve -> orderbook -> publish

Every function below is one step. They are plain functions: they take the
context, do their work, and write one line into the trace. The list at the
bottom is the pipeline. There is no async, no queue and no framework here — see
pipeline.py for the six-line runner.
"""
import json
import logging

import pandas as pd
from battery_utility_calculator import (
    Storage,
    calculate_bidding_curve,
    calculate_multiple_storage_worth,
    calculate_multiple_storage_worth_by_location,
)

from config import DATA_DIR, DEFAULT_COUNTRY, DRY_RUN, LOCATION_COUNTRY, SELLER_LOCATIONS, SOLVER
from forecasting import chronos_forecast
from market.pipeline import MarketContext, run_pipeline
from prosumer import load_profile_metadata

log = logging.getLogger("bidding")

PRICES_CSV = DATA_DIR / "profile_data" / "prices.csv"

# Every candidate storage is offered at this C-rate (kW per kWh of capacity).
C_RATE = 0.2


# --------------------------------------------------------------------------
# Small helpers
# --------------------------------------------------------------------------
def _to_series(value) -> pd.Series | None:
    """Coerce a value to a 1-D, timezone-naive Series."""
    if value is None:
        return None
    if isinstance(value, pd.DataFrame):
        series = value.iloc[:, 0]
    elif isinstance(value, pd.Series):
        series = value
    else:
        series = pd.Series(value)
    if getattr(series.index, "tz", None) is not None:
        series = series.copy()
        series.index = series.index.tz_localize(None)
    return series


def _summarise(name: str, series) -> str:
    """One-line summary of a series for the LLM reasoning prompt."""
    if series is None or len(series) == 0:
        return f"{name}: not available"
    arr = series.to_numpy() if isinstance(series, pd.Series) else pd.Series(series).to_numpy()
    return f"{name}: min={arr.min():.3f}, max={arr.max():.3f}, mean={arr.mean():.3f}, steps={len(arr)}"


def _cached_forecast(cache_path, csv_path, value_col, start, end) -> pd.Series:
    """Use a pre-computed forecast CSV if it exists, otherwise call Chronos."""
    if cache_path.exists():
        series = pd.read_csv(cache_path, index_col=0, parse_dates=True).iloc[:, 0]
        if getattr(series.index, "tz", None) is not None:
            series.index = series.index.tz_localize(None)
        return series[(series.index >= start) & (series.index < end)]

    series = chronos_forecast(str(csv_path), start, end, value_col=value_col)
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    series.to_frame(name=value_col).to_csv(cache_path)
    return series


def locations_in_scope(trading_scope: str, my_location: str) -> list[str]:
    """Which seller locations a buyer may trade with, given their scope setting."""
    if trading_scope == "Community":
        return [my_location]
    if trading_scope == "Country":
        my_country = LOCATION_COUNTRY.get(my_location)
        return [loc for loc in SELLER_LOCATIONS if LOCATION_COUNTRY.get(loc) == my_country]
    return SELLER_LOCATIONS                      # "All"


def forecast_inputs(ctx: MarketContext) -> dict:
    """The five time series the optimiser needs, all on the demand timeline.

    Also used by clearing.py, which recomputes a schedule from the same inputs.
    """
    demand = _to_series(ctx.data["demand_fc"])
    index = demand.index
    prices = ctx.data["prices_fc"]
    return {
        "demand": demand,
        "solar_generation": _to_series(ctx.data["solar_fc"]).reindex(index, method="nearest"),
        "supplier_prices": _to_series(prices.get("supplier")).reindex(index, method="nearest"),
        "eeg_prices": _to_series(prices.get("eeg")).reindex(index, method="nearest"),
        "wholesale_market_prices": _to_series(prices.get("wholesale")).reindex(index, method="nearest"),
        "community": _to_series(prices.get("community")).reindex(index, method="nearest"),
    }


# --------------------------------------------------------------------------
# Steps
# --------------------------------------------------------------------------
def retrieve_profile(ctx: MarketContext):
    metadata = load_profile_metadata(ctx.agent.profile_id)
    storage_size = metadata.get("battery_size_kwh", 0.0)
    ctx.data["storage_size_kwh"] = storage_size
    ctx.data["location"] = metadata.get("location", "unknown").lower()
    role = "seller" if storage_size > 0 else "buyer"
    ctx.log(
        "retrieve_profile",
        f"Fetched the prosumer's battery profile. This user is a {role}.",
        {"battery_size_kwh": storage_size, "location": ctx.data["location"], "role": role},
    )


def retrieve_preferences(ctx: MarketContext):
    ctx.data["preferences"] = ctx.agent.preferences
    ctx.log("retrieve_preferences", "Loaded the user's trading preferences.",
            {"preferences": ctx.agent.preferences})


def retrieve_market_info(ctx: MarketContext):
    products = ctx.market_data.get("products", [])
    product = next((p for p in products if "start_time" in p and "end_time" in p), None)
    if product is None:
        raise ValueError("market_open message carries no product with start_time and "
                         f"end_time: {ctx.market_data!r}")

    start = pd.to_datetime(product["start_time"])
    end = pd.to_datetime(product["end_time"])
    if start.tzinfo is not None:
        start, end = start.tz_convert(None), end.tz_convert(None)
    ctx.data["window"] = {"start": start, "end": end}
    ctx.log("retrieve_market_info", "Extracted the trading window from the market event.",
            {"window_start": str(start), "window_end": str(end)})


def forecast_demand(ctx: MarketContext):
    window = ctx.data["window"]
    pid = ctx.agent.profile_id
    series = _cached_forecast(
        DATA_DIR / f"profile_{pid}_demand_forecasted.csv",
        DATA_DIR / "profile_data" / f"profile_{pid}_demand.csv",
        "load_kw", window["start"], window["end"],
    )
    ctx.data["demand_fc"] = series
    ctx.log("forecast_demand", "Forecast electricity demand for the trading window.",
            {"timesteps": len(series), "mean_kw": round(float(series.mean()), 3)})


def forecast_solar(ctx: MarketContext):
    window = ctx.data["window"]
    pid = ctx.agent.profile_id
    series = _cached_forecast(
        DATA_DIR / f"profile_{pid}_solar_forecasted.csv",
        DATA_DIR / "profile_data" / f"profile_{pid}_solar.csv",
        "solar_kw", window["start"], window["end"],
    )
    ctx.data["solar_fc"] = series
    ctx.log("forecast_solar", "Forecast solar generation for the trading window.",
            {"timesteps": len(series), "peak_kw": round(float(series.max()), 3)})


def forecast_prices(ctx: MarketContext):
    window = ctx.data["window"]
    location = ctx.data.get("location", "unknown")
    country = LOCATION_COUNTRY.get(location, DEFAULT_COUNTRY)

    prices_csv = DATA_DIR / "profile_data" / f"prices_{country}.csv"
    table = pd.read_csv(prices_csv)
    table = table[[c for c in table.columns if not c.startswith("Unnamed")]]
    price_columns = [c for c in table.columns if c != "datetime"]

    prices = {}
    for col in price_columns:
        prices[col] = _cached_forecast(
            DATA_DIR / f"prices_{country}_{col}_forecasted.csv",
            prices_csv, col, window["start"], window["end"],
        )
    ctx.data["prices_fc"] = prices
    ctx.log("forecast_prices", f"Forecast {len(price_columns)} energy price streams for {country}.",
            {"columns": price_columns, "country": country})


def reason_volume_range(ctx: MarketContext):
    """Buyers only: ask the LLM for the upper bound of the volume search range.

    Sellers don't need this — their search range is simply their battery size.
    """
    if ctx.data["storage_size_kwh"] > 0:
        return

    prices = ctx.data.get("prices_fc", {})
    demand = _to_series(ctx.data.get("demand_fc"))
    solar = _to_series(ctx.data.get("solar_fc"))
    net_demand = (demand - solar).clip(lower=0) if demand is not None and solar is not None else demand

    prompt = f"""You are an energy trading coach. Respond in English only.

You are setting the UPPER BOUND of a volume search range [1, max_volume]. The
optimizer sweeps every integer kWh from 1 to max_volume and picks the best one.
Be generous: a range that is too wide costs only a few extra iterations, a range
that is too narrow cuts off better solutions. Minimum max_volume is 5.

The user has NO battery — they rent storage from the community to shift demand
away from expensive grid purchases. Renting beyond peak net demand has no benefit.

Trading preference: {ctx.data['preferences'].get('trading_preference', 'Profit')}
{_summarise('Net demand (demand minus solar)', net_demand)}
{_summarise('Supplier price', _to_series(prices.get('supplier')))}
{_summarise('Wholesale price', _to_series(prices.get('wholesale')))}

Respond with JSON only — no markdown:
{{"max_volume": <integer>, "reasoning": "<brief explanation>"}}"""

    max_volume, reasoning = 10, "fallback — LLM unavailable or returned invalid JSON"
    try:
        response = ctx.agent.llm.invoke([{"role": "user", "content": prompt}], [])
        decision = json.loads(response.strip().replace("```json", "").replace("```", "").strip())
        max_volume = max(int(decision["max_volume"]), 5)
        if net_demand is not None:
            max_volume = min(max_volume, int(net_demand.max()) + 3)
        reasoning = decision.get("reasoning", "")
    except Exception as error:
        log.warning("volume reasoning failed (%s) — falling back to max_volume=10", error)

    ctx.data["max_volume"] = max_volume
    ctx.log("reason_volume_range", "LLM decided the buyer's volume search range.",
            {"max_volume": max_volume, "reasoning": reasoning})


def battery_utility(ctx: MarketContext):
    """Ask the Battery Utility Calculator what each storage size is worth.

    One solve per candidate volume, and for buyers one such sweep per location,
    so the work here is (locations x volumes) linear programs. Both BUC entry
    points are called directly below — what you read is what runs.
    """
    preferences = ctx.data["preferences"]
    battery_kwh = ctx.data["storage_size_kwh"]
    is_buyer = battery_kwh <= 0
    my_location = ctx.data.get("location", "aachen").lower()
    goal = "max_green_energy" if preferences.get("trading_preference") == "Green" else "max_cashflow"

    series = forecast_inputs(ctx)
    community = series.pop("community")

    if is_buyer:
        # Buyers rent storage that physically sits somewhere else, so the sweep
        # runs once per location they are allowed to trade with.
        max_volume = ctx.data.get("max_volume", 10)
        volumes = range(1, max_volume + 1)
        locations = locations_in_scope(preferences.get("trading_scope", "All"), my_location)
        max_tradeable = None

        # NOTE: this entry point returns a plain DataFrame and drops the charge
        # timeseries, so buyers never get a cached schedule — clearing.py
        # recomputes it for the volume that was actually accepted.
        results_df = calculate_multiple_storage_worth_by_location(
            baseline_storage=Storage(id=0, c_rate=C_RATE, volume=battery_kwh),
            storages_to_calculate=[Storage(id=v, c_rate=C_RATE, volume=v) for v in volumes],
            locations_to_calculate=locations,
            community_market_prices={location: community for location in locations},
            my_location=my_location,
            goal=goal,
            solver=SOLVER,
            **series,
        )
        charge_series = {}
    else:
        # Sellers own the battery, so the sweep is over their own capacity and
        # the cap is how much of it they are willing to rent out.
        volumes = range(1, int(battery_kwh) + 1)
        max_tradeable = int(battery_kwh * preferences.get("battery_tradeable_pct", 50) / 100)

        result = calculate_multiple_storage_worth(
            baseline_storage=Storage(id=int(battery_kwh), c_rate=C_RATE, volume=battery_kwh),
            storages_to_calculate=[Storage(id=v, c_rate=C_RATE, volume=v) for v in volumes],
            community_market_prices={my_location: community},
            my_location=my_location,
            is_rented_storage=False,
            goal=goal,
            solver=SOLVER,
            return_charge_timeseries=True,
            **series,
        )
        results_df = result["results_df"]
        charge_series = result.get("storages_to_calc_charge_ts", {})

    columns = ["volume", "worth"] + (["location"] if "location" in results_df.columns else [])
    curve = calculate_bidding_curve(
        volumes_worth=results_df[columns],
        buy_or_sell_side="buyer" if is_buyer else "seller",
    )
    if max_tradeable is not None:
        curve = curve.head(max_tradeable)

    ctx.data["bidding_curve"] = curve
    ctx.data["buc_charge_series"] = charge_series
    ctx.log(
        "battery_utility_calculator",
        "Ran the Battery Utility Calculator to decide how much storage to bid for and at what price.",
        {
            "role": "buyer" if is_buyer else "seller",
            "solves": len(volumes) * (len(locations) if is_buyer else 1),
            "bid_steps": len(curve),
            "total_volume_kwh": round(float(curve["cumulative_volume"].max()), 2),
            "price_range_eur_kwh": [
                round(float(curve["marginal_price_per_kwh"].min()), 4),
                round(float(curve["marginal_price_per_kwh"].max()), 4),
            ],
        },
    )


def make_orderbook(ctx: MarketContext):
    """Turn the bidding curve into a market orderbook — one order per kWh slot."""
    bid_id = ctx.agent.next_bid_id()
    curve = ctx.data["bidding_curve"]
    default_location = ctx.data.get("location", "unknown")

    orderbook = []
    for i, row in curve.iterrows():
        location = row.get("location") or default_location
        orderbook.append({
            "bid_id": f"{ctx.agent.profile_id}_{bid_id}_{location}_{i + 1}",
            "volume": row["volume"],
            "price": row["marginal_price_per_kwh"],
            "location": location,
            "exclusive_id": row.get("exclusive_id"),
        })

    ctx.data["orderbook"] = orderbook
    ctx.log("make_orderbook", "Converted the bidding curve into a market orderbook.",
            {"num_orders": len(orderbook),
             "total_volume_kwh": round(sum(o["volume"] for o in orderbook), 2)})


def publish_bid(ctx: MarketContext):
    orderbook = ctx.data.get("orderbook")
    if not orderbook:
        ctx.log("publish_bid", "No orderbook to publish — step skipped.")
        return
    if DRY_RUN:
        ctx.log("publish_bid", "Dry run — orderbook built but not published.",
                {"num_orders": len(orderbook)})
        return
    ctx.agent.market_client.send_orderbook(orderbook)
    ctx.log("publish_bid", "Submitted the orderbook to the energy market via MQTT.",
            {"num_orders_sent": len(orderbook)})


BIDDING_STEPS = [
    retrieve_profile,
    retrieve_preferences,
    retrieve_market_info,
    forecast_demand,
    forecast_solar,
    forecast_prices,
    reason_volume_range,
    battery_utility,
    make_orderbook,
    publish_bid,
]


def run_bidding(agent, market_data: dict) -> MarketContext:
    """Run the full bidding pipeline for one market-open event."""
    ctx = MarketContext(agent=agent, market_data=market_data)
    run_pipeline(ctx, BIDDING_STEPS, agent.pipeline_status, name="bidding")
    # Remember this run so clearing can reuse the forecasts and schedules, and
    # so the chat assistant can explain the bid.
    agent.last_bidding_data = ctx.data
    agent.last_bid_trace = ctx.trace
    return ctx
