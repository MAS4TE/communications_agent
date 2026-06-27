"""The bidding pipeline — runs when the market opens.

Triggered by a ``market_open`` MQTT message, this works out what to bid for the
upcoming trading window and submits an orderbook to the market:

    preferences -> profile (buyer or seller?) -> trading window
        -> forecast demand, solar and prices
        -> (buyers) reason about how much to search
        -> battery utility calculator -> bidding curve -> orderbook -> publish

Each step records a line in the trace so the chat assistant can explain it.
"""
import json

import pandas as pd

import battery_utility
from battery_utility import Storage
from forecasting import chronos_forecast
from market.flow import MarketContext, run_blocking, run_pipeline
from prosumer import load_profile_metadata
from config import DATA_DIR

PRICES_CSV = DATA_DIR / "profile_data" / "prices.csv"


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
    return chronos_forecast(str(csv_path), start, end, value_col=value_col)


# --------------------------------------------------------------------------
# Steps
# --------------------------------------------------------------------------
async def retrieve_profile(ctx: MarketContext):
    metadata = await run_blocking(load_profile_metadata, ctx.agent.profile_id)
    storage_size = metadata.get("battery_size_kwh", 0.0)
    ctx.data["storage_size_kwh"] = storage_size
    ctx.data["location"] = metadata.get("location", "unknown")
    role = "seller" if storage_size > 0 else "buyer"
    ctx.log(
        "retrieve_profile",
        f"Fetched the prosumer's battery profile. This user is a {role}.",
        {"battery_size_kwh": storage_size, "location": ctx.data["location"], "role": role},
    )


async def retrieve_preferences(ctx: MarketContext):
    ctx.data["preferences"] = ctx.agent.preferences
    ctx.log(
        "retrieve_preferences",
        "Loaded the user's trading preferences.",
        {"preferences": ctx.agent.preferences},
    )


async def retrieve_market_info(ctx: MarketContext):
    products = ctx.market_data.get("products", [])
    product = next(p for p in products if "start_time" in p and "end_time" in p)
    start = pd.to_datetime(product["start_time"])
    end = pd.to_datetime(product["end_time"])
    if start.tzinfo is not None:
        start, end = start.tz_convert(None), end.tz_convert(None)
    ctx.data["window"] = {"start": start, "end": end}
    ctx.log(
        "retrieve_market_info",
        "Extracted the trading window from the market event.",
        {"window_start": str(start), "window_end": str(end)},
    )


async def forecast_demand(ctx: MarketContext):
    window = ctx.data["window"]
    pid = ctx.agent.profile_id
    series = await run_blocking(
        _cached_forecast,
        DATA_DIR / f"profile_{pid}_demand_forecasted.csv",
        DATA_DIR / "profile_data" / f"profile_{pid}_demand.csv",
        "load_kw", window["start"], window["end"],
    )
    ctx.data["demand_fc"] = series
    ctx.log("forecast_demand", "Forecast electricity demand for the trading window.",
            {"timesteps": len(series), "mean_kw": round(float(series.mean()), 3)})


async def forecast_solar(ctx: MarketContext):
    window = ctx.data["window"]
    pid = ctx.agent.profile_id
    series = await run_blocking(
        _cached_forecast,
        DATA_DIR / f"profile_{pid}_solar_forecasted.csv",
        DATA_DIR / "profile_data" / f"profile_{pid}_solar.csv",
        "solar_kw", window["start"], window["end"],
    )
    ctx.data["solar_fc"] = series
    ctx.log("forecast_solar", "Forecast solar generation for the trading window.",
            {"timesteps": len(series), "peak_kw": round(float(series.max()), 3)})


async def forecast_prices(ctx: MarketContext):
    window = ctx.data["window"]
    table = pd.read_csv(PRICES_CSV)
    table = table[[c for c in table.columns if not c.startswith("Unnamed")]]
    price_columns = [c for c in table.columns if c != "datetime"]

    prices = {}
    for col in price_columns:
        prices[col] = await run_blocking(
            _cached_forecast,
            DATA_DIR / f"prices_{col}_forecasted.csv",
            PRICES_CSV, col, window["start"], window["end"],
        )
    ctx.data["prices_fc"] = prices
    ctx.log("forecast_prices", f"Forecast {len(price_columns)} energy price streams.",
            {"columns": price_columns})


async def reason_volume_range(ctx: MarketContext):
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
        response = await run_blocking(ctx.agent.llm.invoke, [{"role": "user", "content": prompt}], [])
        decision = json.loads(response.strip().replace("```json", "").replace("```", "").strip())
        max_volume = max(int(decision["max_volume"]), 5)
        if net_demand is not None:
            max_volume = min(max_volume, int(net_demand.max()) + 3)
        reasoning = decision.get("reasoning", "")
    except Exception as error:
        print(f"BIDDING: volume reasoning failed ({error}), using fallback 10")

    ctx.data["max_volume"] = max_volume
    ctx.log("reason_volume_range", "LLM decided the buyer's volume search range.",
            {"max_volume": max_volume, "reasoning": reasoning})


async def battery_utility(ctx: MarketContext):
    """Run the optimiser and turn the result into a bidding curve."""
    preferences = ctx.data["preferences"]
    full_battery = ctx.data["storage_size_kwh"]
    is_buyer = full_battery <= 0
    goal = "max_green_energy" if preferences.get("trading_preference") == "Green" else "max_cashflow"

    # All series share the demand timeline.
    demand = _to_series(ctx.data["demand_fc"])
    index = demand.index
    prices = ctx.data["prices_fc"]
    common = dict(
        demand=demand,
        solar=_to_series(ctx.data["solar_fc"]).reindex(index, method="nearest"),
        grid_prices=_to_series(prices.get("supplier")).reindex(index, method="nearest"),
        eeg_prices=_to_series(prices.get("eeg")).reindex(index, method="nearest"),
        community_prices=_to_series(prices.get("community")).reindex(index, method="nearest"),
        wholesale_prices=_to_series(prices.get("wholesale")).reindex(index, method="nearest"),
    )

    max_tradeable = None
    if is_buyer:
        max_volume = ctx.data.get("max_volume", 10)
        storages = [Storage(id=i, c_rate=0.2, volume=i) for i in range(1, max_volume + 1)]
    else:
        tradeable_pct = preferences.get("battery_tradeable_pct", 50)
        max_tradeable = int(full_battery * (tradeable_pct / 100))
        storages = [Storage(id=i, c_rate=0.2, volume=i) for i in range(1, int(full_battery) + 1)]

    result = await run_blocking(
        battery_utility.storage_worth,
        baseline_storage=Storage(id=int(full_battery), c_rate=0.2, volume=full_battery),
        storages=storages,
        my_location=ctx.data.get("location", "aachen"),
        is_buyer=is_buyer,
        trading_scope=preferences.get("trading_scope", "All"),
        goal=goal,
        return_charge_timeseries=True,
        **common,
    )

    curve = battery_utility.bidding_curve(result["results_df"], is_buyer=is_buyer, max_tradeable=max_tradeable)
    ctx.data["bidding_curve"] = curve
    ctx.data["buc_charge_series"] = result.get("storages_to_calc_charge_ts", {})
    ctx.log(
        "battery_utility_calculator",
        "Ran the Battery Utility Calculator to decide how much storage to bid for and at what price.",
        {
            "role": "buyer" if is_buyer else "seller",
            "bid_steps": len(curve),
            "total_volume_kwh": round(float(curve["cumulative_volume"].max()), 2),
            "price_range_eur_kwh": [
                round(float(curve["marginal_price_per_kwh"].min()), 4),
                round(float(curve["marginal_price_per_kwh"].max()), 4),
            ],
        },
    )


async def make_orderbook(ctx: MarketContext):
    """Turn the bidding curve into a market orderbook — one order per kWh slot."""
    bid_id = ctx.agent.next_bid_id()
    curve = ctx.data.get("bidding_curve")
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


async def publish_bid(ctx: MarketContext):
    orderbook = ctx.data.get("orderbook")
    if not orderbook:
        ctx.log("publish_bid", "No orderbook to publish — step skipped.")
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


async def run_bidding(agent, market_data: dict) -> MarketContext:
    """Run the full bidding pipeline for one market-open event."""
    ctx = MarketContext(agent=agent, market_data=market_data)
    await run_pipeline(ctx, BIDDING_STEPS, agent.pipeline_status)
    # Remember this run so market clearing can reuse the forecasts and schedules,
    # and so the chat assistant can explain the bid.
    agent.last_bidding_data = ctx.data
    agent.last_bid_trace = ctx.trace
    return ctx
