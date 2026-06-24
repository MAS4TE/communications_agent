# core/pipeline/steps.py
import asyncio
import os
from functools import partial
from concurrent.futures import ThreadPoolExecutor

from core.llm.tools.registry import tool_registry
from core.main_context import GLOBAL_PROFILE_ID
from core.main_context import get_mqtt_agent_assume, get_mqtt_agent_battery

import pandas as pd
from datetime import datetime

from core.llm.tools.chronos_tool import forecast_timeseries_from_csv
from api.services.prosumer.prosumer_service import ProsumerService

from core.domain.chat_session import SolarChatSession
from core.main_context import get_llm

from battery_utility_calculator import calculate_bidding_curve
from battery_utility_calculator import Storage


from requests.auth import HTTPBasicAuth
import requests
import yaml

test_no_fc = False
_BID_COUNTER = 0
_TEST_SEND_DONE = False


DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "data")

# ---------------------------------------------------------------------------
# Bounded thread pool — limits how many CPU-heavy calls run simultaneously.
# ---------------------------------------------------------------------------
THREAD_POOL = ThreadPoolExecutor(max_workers=1)


async def run_blocking(fn, *args, **kwargs):
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(THREAD_POOL, partial(fn, *args, **kwargs))


async def soc_to_power_request(buc_charge_series: dict) -> dict:
    all_socs = pd.concat(buc_charge_series.values(), axis=1)
    soc_total = all_socs.sum(axis=1)

    dt_hours = 0.25
    power_kw = soc_total.diff() / dt_hours
    power_kw = power_kw.fillna(0)
    power_w = power_kw * 1000

    time_steps_s = (soc_total.index - soc_total.index[0]).total_seconds().astype(int)

    return {
        "time_steps": time_steps_s.tolist(),
        "power_rate_w": power_w.tolist(),
    }

async def _summarise_series(name, series):
    if series is None or len(series) == 0:
        return f"{name}: not available"
    import numpy as np
    arr = np.array(series)
    cumulative = np.cumsum(arr)
    breakeven_idx = next((i for i, v in enumerate(cumulative) if v < 0), None)
    return (
        f"{name}: min={arr.min():.3f} €, max={arr.max():.3f} €, "
        f"mean={arr.mean():.3f} €, steps={len(arr)}, "
        f"cumulative breakeven_at_step={breakeven_idx if breakeven_idx is not None else 'never goes negative'}"
    )

def retrieve_step_map():
    return STEP_MAP


# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------

def _to_1d(x):
    if x is None:
        return None
    if isinstance(x, pd.DataFrame):
        if x.shape[1] != 1:
            raise ValueError(f"Expected single-column DataFrame, got {x.shape}")
        series = x.iloc[:, 0]
    elif isinstance(x, pd.Series):
        series = x
    elif hasattr(x, "ndim"):
        series = pd.Series(x)
    else:
        series = pd.Series(x)

    if hasattr(series.index, "tz") and series.index.tz is not None:
        series = series.copy()
        series.index = series.index.tz_localize(None)

    return series


def _print_bid_summary(label, result):
    worth = result["single_worth"]
    curve_df = pd.DataFrame(result["bidding_curve"])
    print(f"\n[{label}] worth: €{worth:.4f}")
    print(curve_df.to_string(index=False))


# ---------------------------------------------------------------------------
# STEPS — market_open sequence
# ---------------------------------------------------------------------------

async def step1(dto):
    dto["step1"] = "done"
    print("STEPS: Step 1 completed")
    dto.log_step("init", "Pipeline initialized and ready to run. ")
    return dto

async def step_test_llm(dto):
    from core.main_context import get_llm
    from core.domain.chat_session import SolarChatSession

    llm = get_llm()
    if llm is None:
        print("STEPS: step_test_llm — no LLM found, skipping")
        dto.log_step("test_llm", "No LLM found.")
        return dto

    print("STEPS: step_test_llm — LLM found, sending test message...")

    session = SolarChatSession(llm=llm, prompt="You are a helpful assistant.")
    response = await run_blocking(session.process_message, "Say hello in one sentence.")

    # print(f"STEPS: step_test_llm — response: {response}")
    dto["llm_test_response"] = response
    dto.log_step("test_llm", "Verified LLM is reachable by sending a test message.")
    return dto


async def step_retrieve_preferences(dto):
    service = ProsumerService()
    preferences = service.get_preferences()

    preferences["trading_preference"]="Green"

    dto["preferences"] = preferences
    if dto.get("storage_size_kwh", 0) > 0:
        dto["battery_tradeable_pct"] = preferences.get("battery_tradeable_pct", 50)

    # preferences["trading_preference"] = "Green"
    print("STEPS: preferences retrieved:", preferences)
    

    dto.log_step(
        "retrieve_preferences",
        "Loaded the user's trading preferences from the database.",
        {
            "preference": preferences,
        }
    )
    return dto


async def step_retrieve_profile(dto):
    tool_get_profile = next(
        t for t in tool_registry.tools if t.__name__ == "get_profile_metadata"
    )
    result_profile = await run_blocking(tool_get_profile, GLOBAL_PROFILE_ID)
    print("result profile", result_profile)
    dto["storage_size_kwh"] = result_profile.get("battery_size_kwh", 0.0)
    dto["location"] = result_profile.get("location", "unknown")
    print(f"STEPS: location = {dto['location']}")
    # print(dto["storage_size_kwh"])
    role = "seller" if dto["storage_size_kwh"] > 0 else "buyer"
    print('ROLE: ', role)

    dto.log_step(
        "retrieve_profile",
        f"Fetched the prosumer's battery profile. This user is a {role}.",
        {
            "tool": "get_profile_metadata",
            "profile": result_profile,
            "battery_size_kwh": dto["storage_size_kwh"],
            "role": role,
        }
    )

    return dto


async def step_market_open(dto):
    print("PIPELINE: Market opened step triggered!")
    # print("market data", dto["market_data"])
    dto["market_open_processed"] = True
    dto.log_step("market_open", "Received and acknowledged the market-open event.")
    return dto


async def step_retrieve_market_info(dto):
    market_info = dto["market_data"]
    products = market_info.get("products", [])
    starts, ends = [], []
    for p in products:
        if "start_time" in p and "end_time" in p:
            starts.append(pd.to_datetime(p["start_time"]))
            ends.append(pd.to_datetime(p["end_time"]))

    dto["market_window"] = {"start": starts[0], "end": ends[0]}
    # print("market window", dto["market_window"])

    dto.log_step(
        "retrieve_market_info",
        "Extracted the trading window from the market event.",
        {
            "window_start": str(starts[0]),
            "window_end":   str(ends[0]),
        }
    )
    return dto


async def step_fc_demand(dto):
    print("STEPS: step_fc_demand started")
    start = pd.to_datetime(dto["market_window"]["start"])
    end = pd.to_datetime(dto["market_window"]["end"])

    if test_no_fc == True:
        dr = pd.date_range(start, end, freq="15min")
        df = pd.DataFrame()
        df.index = dr
        df["load_kw"] = 5
        dto["demand_fc"] = df["load_kw"]
        return dto

    cache_path = os.path.join(DATA_DIR, f"profile_{GLOBAL_PROFILE_ID}_demand_forecasted.csv")
    if os.path.exists(cache_path):
        print(f"STEPS: demand forecast loaded from cache")
        # df = pd.read_csv(cache_path, index_col=0, parse_dates=True)
        # dto["demand_fc"] = df.iloc[:, 0]
        df = pd.read_csv(cache_path, index_col=0, parse_dates=True)
        series = df.iloc[:, 0]
        series.index = series.index.tz_localize(None)
        dto["demand_fc"] = series[(series.index >= str(start)) & (series.index < str(end))]
        series = dto["demand_fc"]
        dto.log_step(
            "forecast_demand",
            "Loaded demand forecast from cache (pre-computed).",
            {
                "timesteps": len(series),
                "mean_kw":   round(float(series.mean()), 3),
                "max_kw":    round(float(series.max()), 3),
                "min_kw":    round(float(series.min()), 3),
            }
        )
        return dto

    demand_fc = await run_blocking(
        forecast_timeseries_from_csv,
        csv_path=f"data/profile_data/profile_{GLOBAL_PROFILE_ID}_demand.csv",
        start=start,
        end=end,
        history_days=1,
        value_col="load_kw",
        save_csv=True,
        csv_filename="data/demand_forecast_test1.csv",
    )

    # print("STEPS: Chronos demand returned, length:", len(demand_fc["median"]))
    timestamps = pd.to_datetime(list(demand_fc["timestamps"]), errors="raise")
    dto["demand_fc"] = pd.Series(demand_fc["median"], index=timestamps)
    # print("STEPS: demand forecast\n", dto["demand_fc"])

    series = dto["demand_fc"]
    dto.log_step(
        "forecast_demand",
        "Forecast electricity demand for the trading window using the Chronos model.",
        {
            "timesteps": len(series),
            "mean_kw":   round(float(series.mean()), 3),
            "max_kw":    round(float(series.max()), 3),
            "min_kw":    round(float(series.min()), 3),
        }
    )
    return dto


async def step_fc_solar(dto):
    print("STEPS: step_fc_solar started")
    start = pd.to_datetime(dto["market_window"]["start"])
    end = pd.to_datetime(dto["market_window"]["end"])

    if test_no_fc == True:
        dr = pd.date_range(start, end, freq="15min")
        df = pd.DataFrame()
        df.index = dr
        df["solar_gen_kw"] = 5
        dto["solar_fc"] = df["solar_gen_kw"]
        return dto

    cache_path = os.path.join(DATA_DIR, f"profile_{GLOBAL_PROFILE_ID}_solar_forecasted.csv")
    if os.path.exists(cache_path):
        print(f"STEPS: solar forecast loaded from cache")
        df = pd.read_csv(cache_path, index_col=0, parse_dates=True)
        series = df.iloc[:, 0]
        series.index = series.index.tz_localize(None)
        dto["solar_fc"] = series[(series.index >= start) & (series.index < end)]
        dto.log_step(
            "forecast_solar",
            "Loaded solar forecast from cache (pre-computed).",
            {
                "timesteps": len(series),
                "mean_kw":   round(float(series.mean()), 3),
                "peak_kw":   round(float(series.max()), 3),
                "min_kw":    round(float(series.min()), 3),
            }
        )
        return dto

    solar_fc = await run_blocking(
        forecast_timeseries_from_csv,
        csv_path=f"data/profile_data/profile_{GLOBAL_PROFILE_ID}_solar.csv",
        start=start,
        end=end,
        history_days=1,
        value_col="solar_kw",
        save_csv=True,
        csv_filename="data/solar_forecast_test1.csv",
    )

    # print("STEPS: Chronos solar returned, length:", len(solar_fc["median"]))
    timestamps = pd.to_datetime(list(solar_fc["timestamps"]), errors="raise")
    dto["solar_fc"] = pd.Series(solar_fc["median"], index=timestamps)
    # print("STEPS: solar forecast\n", dto["solar_fc"])

    series = dto["solar_fc"]
    dto.log_step(
        "forecast_solar",
        "Forecast solar generation for the trading window using the Chronos model.",
        {
            "timesteps": len(series),
            "mean_kw":   round(float(series.mean()), 3),
            "peak_kw":   round(float(series.max()), 3),
            "min_kw":    round(float(series.min()), 3),
        }
    )
    return dto


async def step_fc_prices(dto):
    print("STEPS: step_fc_prices started")
    start = pd.to_datetime(dto["market_window"]["start"])
    end = pd.to_datetime(dto["market_window"]["end"])

    if test_no_fc == True:
        dr = pd.date_range(start, end, freq="15min")
        df = pd.DataFrame()
        df.index = dr
        df["supplier"] = 5
        df["eeg"] = 5
        df["wholesale"] = 5
        df["community"] = 0
        dto["prices_fc"] = {"supplier": df["supplier"], "eeg": df["eeg"], "wholesale": df["wholesale"], "community": df["community"]}
        return dto

    price_csv = "data/profile_data/prices.csv"
    df = pd.read_csv(price_csv)
    for col in df.columns:
        if "Unnamed: 0" in col:
            df = df.drop(columns=col)

    price_columns = [c for c in df.columns if c != "datetime"]
    # print("STEPS: price columns to forecast:", price_columns)

    prices_fc = {}
    for col in price_columns:
        cache_path = os.path.join(DATA_DIR, f"prices_{col}_forecasted.csv")
        if os.path.exists(cache_path):
            # print(f"STEPS: price '{col}' loaded from cache")
            df_cache = pd.read_csv(cache_path, index_col=0, parse_dates=True)
            series = df_cache.iloc[:, 0]
            series.index = series.index.tz_localize(None)

            prices_fc[col] = series[(series.index >= start) & (series.index < end)]
            continue

        # print(f"STEPS: forecasting price column '{col}'")
        result = await run_blocking(
            forecast_timeseries_from_csv,
            csv_path=price_csv,
            start=start,
            end=end,
            history_days=1,
            value_col=col,
            save_csv=True,
            csv_filename=f"data/{col}_forecast_test.csv",
        )
        # print(f"STEPS: Chronos returned {len(result['median'])} points for '{col}'")
        timestamps = pd.to_datetime(result["timestamps"], errors="raise")
        prices_fc[col] = pd.Series(result["median"], index=timestamps)

    dto["prices_fc"] = prices_fc

    # print("STEPS: all price forecasts done")
    # for k, v in dto["prices_fc"].items():
    #     print(k, v.head())

    dto.log_step(
        "forecast_prices",
        f"Forecast {len(price_columns)} energy price streams for the trading window.",
        {
            "columns_forecast": price_columns,
            "summaries": {
                col: {"mean": round(float(s.mean()), 4), "max": round(float(s.max()), 4)}
                for col, s in prices_fc.items()
            },
        }
    )
    return dto


def _summarise_series(name, series):
    if series is None or len(series) == 0:
        return f"{name}: not available"
    import numpy as np
    arr = np.array(series)
    cumulative = np.cumsum(arr)
    breakeven_idx = next((i for i, v in enumerate(cumulative) if v < 0), None)
    return (
        f"{name}: min={arr.min():.3f}, max={arr.max():.3f}, "
        f"mean={arr.mean():.3f}, steps={len(arr)}, "
        f"cumulative breakeven_at_step={breakeven_idx if breakeven_idx is not None else 'never goes negative'}"
    )


async def step_reason_buc_range(dto):
    print("STEPS: step_reason_buc_range started")

    role = "seller" if dto["storage_size_kwh"] > 0 else "buyer"

    llm = get_llm()
    if llm is None:
        print("STEPS: no LLM available, using fallback max_volume=10")
        dto["buc_max_volume"] = 10
        return dto

    preferences = dto.get("preferences", {})
    trading_preference = preferences.get("trading_preference", "unknown")
    market_window = dto.get("market_window", {})

    if role == "seller":
        storage_size  = dto["storage_size_kwh"]
        tradeable_pct = preferences.get("battery_tradeable_pct", 50)
        max_tradeable = int(storage_size * (tradeable_pct / 100))

        prices_fc  = dto.get("prices_fc", {})
        supplier   = _to_1d(prices_fc.get("supplier"))
        wholesale  = _to_1d(prices_fc.get("wholesale"))
        eeg        = _to_1d(prices_fc.get("eeg"))
        solar_fc   = _to_1d(dto.get("solar_fc"))
        demand_fc  = _to_1d(dto.get("demand_fc"))

        data_summary = (
            f"Battery capacity: {storage_size} kWh\n"
            f"Tradeable portion: {tradeable_pct}% → max {max_tradeable} kWh\n"
            f"{_summarise_series('Supplier price (grid cost)', supplier)}\n"
            f"{_summarise_series('Wholesale price (revenue if sold)', wholesale)}\n"
            f"{_summarise_series('EEG tariff', eeg)}\n"
            f"{_summarise_series('Solar generation', solar_fc)}\n"
            f"{_summarise_series('Demand', demand_fc)}"
        )
        role_context = f"""The user OWNS a battery ({storage_size} kWh, {tradeable_pct}% tradeable = max {max_tradeable} kWh).
        They earn revenue by renting storage to buyers.
        Revenue per kWh offered comes from the wholesale price; cost is the supplier price.
        Buyers' willingness to pay declines with each additional kWh (downward sloping curve).
        Stop searching where marginal wholesale revenue no longer covers marginal supplier cost.
        Hard ceiling: never exceed {max_tradeable} kWh."""

    else:
        demand_fc  = _to_1d(dto.get("demand_fc"))
        solar_fc   = _to_1d(dto.get("solar_fc"))
        prices_fc  = dto.get("prices_fc", {})
        supplier   = _to_1d(prices_fc.get("supplier"))
        wholesale  = _to_1d(prices_fc.get("wholesale"))
        eeg        = _to_1d(prices_fc.get("eeg"))

        if demand_fc is not None and solar_fc is not None:
            net_demand = (demand_fc - solar_fc).clip(lower=0)
        elif demand_fc is not None:
            net_demand = demand_fc
        else:
            net_demand = None

        data_summary = (
            f"{_summarise_series('Net demand (demand minus solar)', net_demand)}\n"
            f"{_summarise_series('Supplier price (grid cost avoided by using storage)', supplier)}\n"
            f"{_summarise_series('Wholesale price (storage opportunity cost)', wholesale)}\n"
            f"{_summarise_series('EEG tariff', eeg)}"
        )
        role_context = """The user has NO battery — they rent storage from the community
        to shift their net demand away from expensive grid purchases.
        Each additional kWh of rented storage covers less valuable demand (curve slopes down).
        Renting is only worth it while supplier price exceeds the rental cost.
        The max_volume should reflect peak net demand — renting beyond that has no benefit."""

    prompt = f"""You are an energy trading coach. Always respond in English ONLY.
    Do not take into account the expert level of the prosumer in this reasoning.

    You are setting the UPPER BOUND of a volume search range [1, max_volume].
    The optimizer sweeps every integer kWh from 1 to max_volume and picks the best one.
    You are NOT picking the exact bid — you are defining how far the search goes.

    Be GENEROUS with the upper bound. A range that is too wide costs only a few extra
    optimizer iterations. A range that is too narrow cuts off better solutions entirely.
    Minimum max_volume is 5 regardless of demand or battery size.

    {role_context}

    Trading preferences:
    - "Profit": optimize for cost/revenue efficiency — stop where marginal return is near zero
    - "Green": prioritize renewable usage — search a bit wider, accept thinner margins

    Trading preference: {trading_preference}
    Market window: start={market_window.get('start')}, end={market_window.get('end')}

    {data_summary}

    Respond with JSON only — no markdown:
    {{"max_volume": <integer>, "reasoning": "<brief explanation referencing the data above>"}}"""

    session = SolarChatSession(llm=llm, prompt=prompt)
    reasoning_text = "fallback — LLM unavailable or returned invalid JSON"

    print(f"STEPS: asking LLM to reason about BUC volume range (role={role})...")
    try:
        import json as _json
        response = await run_blocking(session.process_message, prompt)
        # print(f"STEPS: LLM response:\n{response}\n")

        clean    = response.strip().replace("```json", "").replace("```", "").strip()
        decision = _json.loads(clean)

        max_vol = max(int(decision["max_volume"]), 5)

        if role == "seller":
            max_vol = min(max_vol, max_tradeable)
        elif net_demand is not None:
            max_vol = min(max_vol, int(net_demand.max()) + 3)

        dto["buc_max_volume"] = max_vol
        reasoning_text = decision.get("reasoning", "")
        # print(f"STEPS: agent (role={role}) decided BUC range: 1–{max_vol} kWh")
        # print(f"STEPS: reasoning: {reasoning_text}")

    except Exception as e:
        print(f"STEPS: reasoning step failed ({e}), using fallback max_volume=10")
        dto["buc_max_volume"] = 10

    dto.log_step(
        "reason_buc_range",
        f"LLM decided the BUC volume search range for role={role}.",
        {"role": role, "max_volume": dto["buc_max_volume"], "reasoning": reasoning_text},
    )
    return dto


async def step_battery_utility_calculator(dto):
    print("=" * 60)
    print("STEPS: step_battery_utility_calculator started")
    print("=" * 60)

    demand_series    = _to_1d(dto.get("demand_fc"))
    solar_series     = _to_1d(dto.get("solar_fc"))
    grid_prices      = _to_1d(dto.get("prices_fc", {}).get("supplier"))
    eeg_prices       = _to_1d(dto.get("prices_fc", {}).get("eeg"))
    community_prices = _to_1d(dto.get("prices_fc", {}).get("community"))
    wholesale_prices = _to_1d(dto.get("prices_fc", {}).get("wholesale"))

    demand_index     = demand_series.index
    solar_series     = solar_series.reindex(demand_index, method="nearest")
    grid_prices      = grid_prices.reindex(demand_index, method="nearest")
    eeg_prices       = eeg_prices.reindex(demand_index, method="nearest")
    community_prices = community_prices.reindex(demand_index, method="nearest")
    wholesale_prices = wholesale_prices.reindex(demand_index, method="nearest")

    common_kwargs = dict(
        demand_series=demand_series,
        solar_series=solar_series,
        grid_prices=grid_prices,
        eeg_prices=eeg_prices,
        community_prices=community_prices,
        wholesale_prices=wholesale_prices,
    )

    buc_tool = next(
        t for t in tool_registry.tools if t.__name__ == "battery_utility_calculator"
    )

    full_battery_kwh  = dto.get("storage_size_kwh", 0)
    my_location       = dto.get("location", "aachen").lower()
    trading_scope     = dto.get("preferences", {}).get("trading_scope", "All")
    trading_preference = dto.get("preferences", {}).get("trading_preference", "Profit")
    goal              = "max_green_energy" if trading_preference == "Green" else "max_cashflow"

    if full_battery_kwh > 0:
        tradeable_pct         = dto.get("preferences", {}).get("battery_tradeable_pct", 50)
        max_tradeable         = int(full_battery_kwh * (tradeable_pct / 100))
        side                  = "seller"
        storages_to_calculate = [Storage(id=i, c_rate=0.2, volume=i) for i in range(1, int(full_battery_kwh) + 1)]
    else:
        side  = "buyer"
        dto   = await step_reason_buc_range(dto)
        max_volume            = dto.get("buc_max_volume", 10)
        storages_to_calculate = [Storage(id=i, c_rate=0.2, volume=i) for i in range(1, max_volume + 1)]

    result = await run_blocking(
        buc_tool,
        baseline_storage=Storage(id=full_battery_kwh, c_rate=0.2, volume=full_battery_kwh),
        storages_to_calculate=storages_to_calculate,
        goal=goal,
        return_charge_timeseries=True,
        my_location=my_location,
        is_rented_storage=(side == "buyer"),
        trading_scope=trading_scope,
        **common_kwargs,
    )

    results_df = result["results_df"]
    cols = ["volume", "worth"]
    if "location" in results_df.columns:
        cols.append("location")
    bidding_curve = calculate_bidding_curve(
        volumes_worth=results_df[cols],
        buy_or_sell_side=side,
    )
    if side == "seller":
        bidding_curve = bidding_curve.head(max_tradeable)

    dto["bidding_curve"]     = bidding_curve
    dto["buc_charge_series"] = result.get("storages_to_calc_charge_ts", {})

    dto.log_step(
        "battery_utility_calculator",
        "Ran the Battery Utility Calculator to find how much storage capacity to bid for and at what price.",
        {
            "tool":                "battery_utility_calculator",
            "role":                side,
            "trading_scope":       trading_scope,
            "bid_steps":           len(bidding_curve),
            "total_volume_kwh":    round(float(bidding_curve["cumulative_volume"].max()), 2),
            "price_range_eur_kwh": [
                round(float(bidding_curve["marginal_price_per_kwh"].min()), 4),
                round(float(bidding_curve["marginal_price_per_kwh"].max()), 4),
            ],
        }
    )

    return dto


async def step_set_make_orderbook(dto):
    print("STEPS: ENTER MAKE ORDERBOOK STEP")

    # dto["bid_id"] = 0 if dto.get("bid_id") is None else dto["bid_id"] + 1
    global _BID_COUNTER
    dto["bid_id"] = _BID_COUNTER
    _BID_COUNTER += 1

    bidding_curve = dto.get("bidding_curve")

    if bidding_curve is None or bidding_curve.empty:
        print("STEPS: NO BIDDING CURVE FOUND — orderbook will be empty")
        dto["orderbook"] = []
        return dto

    # print(f"STEPS: building orderbook from {len(bidding_curve)} curve steps ...")

    orderbook = []
    for i, row in bidding_curve.iterrows():
        location = row.get("location") or dto.get("location", "uknown")
        order = {
            "bid_id": f"{GLOBAL_PROFILE_ID}_{dto['bid_id']}_{location}_{i + 1}",
            # "bid_id": f"{GLOBAL_PROFILE_ID}_{dto['bid_id']}_{i + 1}",
            # "slot":    i + 1,
            "volume":  row["volume"],
            "price":   row["marginal_price_per_kwh"],
        }
        if location:
            order["location"] = location
            order["exclusive_id"] = row.get("exclusive_id")
        orderbook.append(order)
        # print(f"  slot {order['slot']:>3}  |  volume={order['volume']:.1f} kWh  |  price={order['price']:.4f} EUR/kWh")

    dto["orderbook"] = orderbook

    print(f"STEPS: FINAL ORDERBOOK — {len(orderbook)} bids | "
          f"total volume: {sum(o['volume'] for o in orderbook):.1f} kWh | "
          f"price range: {min(o['price'] for o in orderbook):.4f} – "
          f"{max(o['price'] for o in orderbook):.4f} EUR/kWh")

    dto.log_step(
        "make_orderbook",
        "Converted the bidding curve into a market orderbook — one order per kWh slot.",
        {
            "num_orders":        len(orderbook),
            "total_volume_kwh":  round(sum(o["volume"] for o in orderbook), 2),
            "price_min_eur_kwh": round(min(o["price"] for o in orderbook), 4),
            "price_max_eur_kwh": round(max(o["price"] for o in orderbook), 4),
        }
    )

    return dto

async def step_publish_bid(dto):
    print("STEPS: step_publish_bid started")

    orderbook = dto.get("orderbook")

    if not orderbook:
        print("STEPS: no orderbook to publish")
        dto.log_step("publish_bid", "No orderbook to publish — step skipped.")
        return dto

    # print("STEPS: publishing orderbook:", orderbook)

    mqtt_agent_assume = get_mqtt_agent_assume()
    mqtt_agent_assume.send_orderbook_to_market(orderbook)

    # print("STEPS: bid published successfully")

    dto.log_step(
        "publish_bid",
        "Submitted the orderbook to the energy market via MQTT.",
        {"num_orders_sent": len(orderbook)}
    )
    return dto


# ---------------------------------------------------------------------------
# STEPS — debug / utility
# ---------------------------------------------------------------------------

async def time_tool_step(dto):
    print("Tools in registry:")
    for t in tool_registry.tools:
        print("-", t.__name__)

    tool = next(t for t in tool_registry.tools if t.__name__ == "get_current_time")
    result = await run_blocking(tool)
    dto["current_time"] = result["current_time"]

    dto.log_step(
        "get_current_time",
        "Fetched the current time from the time tool.",
        {"tool": "get_current_time", "current_time": result["current_time"]}
    )
    return dto


async def step2(dto):
    print("Step 2 sees current_time:", dto.get("current_time"))
    dto["step2"] = "done"
    print("STEPS: Step 2 completed")
    dto.log_step("step2", "Debug step 2 completed.")
    return dto


async def step3(dto):
    dto["step3"] = "done"
    print("STEPS: All steps completed")
    dto.log_step("pipeline_complete", "All pipeline steps completed successfully.")
    return dto


# ---------------------------------------------------------------------------
# STEPS — market_clearing sequence
# ---------------------------------------------------------------------------

async def step4_retrieve_market_clearing_info(dto):
    market_data = dto.get("market_data")
    orderbook = market_data.get("orderbook", [])

    role = "seller" if dto.get("storage_size_kwh", 0) > 0 else "buyer"

    accepted_orders = [o for o in orderbook if abs(o.get("accepted_volume", 0)) > 0]
    rejected_orders = [o for o in orderbook if abs(o.get("accepted_volume", 0)) == 0]
    accepted_volume = sum(abs(o["accepted_volume"]) for o in accepted_orders)
    clearing_price  = orderbook[0]["accepted_price"] if orderbook else None

    dto.log_step(
        "market_clearing",
        "Received the market clearing result.",
        {
            "role":                   role,
            "bids_submitted":         len(orderbook),
            "bids_accepted":          len(accepted_orders),
            "bids_rejected":          len(rejected_orders),
            "all_accepted":           len(rejected_orders) == 0,
            "accepted_volume_kwh":    round(accepted_volume, 2),
            "clearing_price_eur_kwh": round(clearing_price, 6) if clearing_price else None,
            "average_bid_price":      round(sum(o["price"] for o in orderbook) / len(orderbook), 6) if orderbook else None,
            "paid_vs_bid":            "paid clearing price, which was lower than bid — buyer saved money" if role == "buyer" and clearing_price and clearing_price < orderbook[0]["price"] else "paid as bid",
            "outcome_summary":        f"All {len(orderbook)} bids accepted, {accepted_volume:.1f} kWh traded at {clearing_price:.6f} €/kWh" if len(rejected_orders) == 0 else f"{len(accepted_orders)} of {len(orderbook)} bids accepted"
        }
    )
    return dto

# if the accepted volume is only a partial bid, re-run BUC for the correct volume
 
async def _run_buc_for_volume(
    dto,
    volume_kwh: float,
    demand_series: pd.Series,
    solar_series: pd.Series,
    grid_prices: pd.Series,
    eeg_prices: pd.Series,
    community_prices: pd.Series,
    wholesale_prices: pd.Series,
) -> dict:
    """Fallback: run BUC for a single exact volume and return a power_request dict."""
    print(f"STEPS: _run_buc_for_volume — running BUC for exact volume {volume_kwh} kWh")

    trading_preference = dto.get("preferences", {}).get("trading_preference", "Profit")
    goal = "max_green_energy" if trading_preference == "Green" else "max_cashflow"

    buc_tool = next(
        t for t in tool_registry.tools if t.__name__ == "battery_utility_calculator"
    )

    my_location = dto.get("location", "aachen").lower()
    role = "seller" if dto.get("storage_size_kwh", 0) > 0 else "buyer"

    result = await run_blocking(
        buc_tool,
        baseline_storage=Storage(id=0, c_rate=0.2, volume=0),
        storages_to_calculate=[Storage(id=volume_kwh, c_rate=0.2, volume=volume_kwh)],
        goal=goal,
        return_charge_timeseries=True,
        my_location=my_location,
        is_rented_storage=(role == "buyer"),
        trading_scope=dto.get("preferences", {}).get("trading_scope", "All"),
        demand_series=demand_series,
        solar_series=solar_series,
        grid_prices=grid_prices,
        eeg_prices=eeg_prices,
        community_prices=community_prices,
        wholesale_prices=wholesale_prices,
    )

    charge_series = result.get("storages_to_calc_charge_ts", {})
    power_request = await soc_to_power_request(charge_series)
    print(f"STEPS: _run_buc_for_volume — done, {len(power_request['time_steps'])} timesteps")
    return power_request

# ---------------------------------------------------------------------------
# step_publish_battery_schedule  (buyers only, matched volume)
# ---------------------------------------------------------------------------
 
async def step_publish_battery_schedule_old(dto):
    print("STEPS: step_publish_battery_schedule started")

    tool_get_profile = next(
        t for t in tool_registry.tools if t.__name__ == "get_profile_metadata"
    )
    result_profile = await run_blocking(tool_get_profile, GLOBAL_PROFILE_ID)
    storage_size_kwh = result_profile.get("battery_size_kwh", 0.0)

    print(f"STEPS: GLOBAL_PROFILE_ID={GLOBAL_PROFILE_ID}, battery_size_kwh={storage_size_kwh}")

    if storage_size_kwh > 0:
        print("STEPS: this is a seller, skipping battery schedule publishing (buyers only)")
        return dto

    step = next((s for s in dto.trace if s["step"] == "market_clearing"), None)
    if step is None:
        print("STEPS: no market_clearing trace found, skipping")
        return dto

    accepted_volume_kwh = step["metadata"].get("accepted_volume_kwh", 0)
    print(f"STEPS: accepted_volume_kwh from clearing = {accepted_volume_kwh}")

    if accepted_volume_kwh == 0:
        print("STEPS: accepted volume is 0, no schedule to send")
        dto.log_step("publish_battery_schedule", "No volume accepted — schedule not sent.")
        return dto

    buc_charge_series = dto.get("buc_charge_series")
    if not buc_charge_series:
        print("STEPS: no buc_charge_series found, skipping")
        dto.log_step("publish_battery_schedule", "No SOC series found — step skipped.")
        return dto

    print(f"STEPS: buc_charge_series keys available = {list(buc_charge_series.keys())}")

    matched_series = buc_charge_series.get(accepted_volume_kwh)
    if matched_series is not None:
        print(f"STEPS: exact match found for volume={accepted_volume_kwh} kWh — using cache")
        power_request = await soc_to_power_request({accepted_volume_kwh: matched_series})
        source = f"cached (exact match={accepted_volume_kwh} kWh)"
    else:
        print(f"STEPS: no exact match for {accepted_volume_kwh} kWh — re-running BUC")
        power_request = await _run_buc_for_volume(dto, accepted_volume_kwh)
        source = f"re-computed BUC for exact volume={accepted_volume_kwh} kWh"

    print(f"STEPS: power request — {len(power_request['time_steps'])} timesteps, "
          f"first power: {power_request['power_rate_w'][0]:.2f} W")

    # mqtt_agent_battery = get_mqtt_agent_battery()
    # mqtt_agent_battery.send_power_request_to_battery(power_request)

    # with open("src/mas4te_restapi_key.yml") as f:
    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "mas4te_restapi_key.yml")) as f:
        config = yaml.safe_load(f)

    user = config["api"]["username"]
    password = config["api"]["password"]
    
    r = requests.post(
        url="https://mas4te.nowum.fh-aachen.de/brp-api/power_request",
        auth=HTTPBasicAuth(username=user, password=password),
        json=power_request,
    )

    print(r.status_code)
    print(r.json())



    print("STEPS: battery schedule published successfully")
    dto.log_step(
        "publish_battery_schedule",
        "Sent the battery charging/discharging schedule to the physical battery via MQTT.",
        {
            "accepted_volume_kwh": accepted_volume_kwh,
            "schedule_source":     source,
            "timesteps":           len(power_request["time_steps"]),
            "first_power_w":       round(power_request["power_rate_w"][0], 2),
        }
    )
    return dto


async def test_buyer_schedule(dto):
    print('STEPS: step test send')

    if dto.get("storage_size_kwh", 0) > 0:
        print("STEPS: this is a seller, skipping battery schedule publishing (buyers only)")
        return dto

    buc_charge_series = dto.get("buc_charge_series")
    if not buc_charge_series:
        print("STEPS: no buc_charge_series found, skipping")
        dto.log_step("publish_battery_schedule", "No SOC series found — step skipped.")
        return dto

    step = next((s for s in dto.trace if s["step"] == "market_clearing"), None)
    accepted_volume = step["metadata"].get("accepted_volume_kwh", 0) if step else 0

    if accepted_volume == 0:
        print("STEPS: accepted volume is 0, no schedule to send")
        dto.log_step("publish_battery_schedule", "No volume accepted — schedule not sent.")
        return dto

    matched_series = buc_charge_series.get(accepted_volume)
    if matched_series is not None:
        print(f"STEPS: exact match found for volume={accepted_volume} kWh — using cache")
        df = matched_series
        source = f"cached (exact match={accepted_volume} kWh)"
    else:
        print(f"STEPS: no exact match for {accepted_volume} kWh — re-running BUC")
        df = await _run_buc_for_volume(dto, accepted_volume)
        source = f"re-computed BUC for exact volume={accepted_volume} kWh"
        timesteps = df.index.astype(str).tolist()

    payload = {
        "request_id": os.environ.get("AGENT_ID", "unknown"),
        "time_steps": timesteps,
        "eeg": df["soc_eeg"].tolist(),
        "wholesale": df["soc_wholesale"].tolist(),
        "community": df["soc_community"].tolist(),
        "home": df["soc_home"].tolist()
    }

    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "mas4te_restapi_key.yml")) as f:
        config = yaml.safe_load(f)

    user = config["api"]["username"]
    password = config["api"]["password"]

    r = requests.post(
    url="https://mas4te.nowum.fh-aachen.de/brp-api/power_request",
    auth=HTTPBasicAuth(username=user, password=password),
    json=payload,
    params={
        "is_real_world_test": False,  # False = simulation mode (no real battery interaction)
                                      # True  = real-time mode (sends schedule to physical battery)
    },
)

    print(r.status_code)
    try:
        print(r.json())
    except Exception:
        print("Response body:", r.text)

    print(f"STEPS: step_test_send — sent {len(timesteps)} timesteps")

    dto.log_step(
        "publish_battery_schedule",
        "Sent the battery charging/discharging schedule to the API.",
        {
            "accepted_volume_kwh": accepted_volume,
            "schedule_source": source,
            "timesteps": len(timesteps),
        }
    )
    return dto


async def _publish_schedule_buyer(dto) -> None:
    """
    Sends SOC schedule to the REST API for buyers.
    Buyers have no physical battery — they rent storage from the community.
    The schedule tells the API how the rented storage should be used.
    """
    buc_charge_series = dto.get("buc_charge_series")
    if not buc_charge_series:
        print("STEPS: no buc_charge_series found, skipping")
        dto.log_step("publish_battery_schedule", "No SOC series found — step skipped.")
        return

    step = next((s for s in dto.trace if s["step"] == "market_clearing"), None)
    accepted_volume = step["metadata"].get("accepted_volume_kwh", 0) if step else 0

    if accepted_volume == 0:
        print("STEPS: accepted volume is 0, no schedule to send")
        dto.log_step("publish_battery_schedule", "No volume accepted — schedule not sent.")
        return

    matched_series = buc_charge_series.get(accepted_volume)
    if matched_series is not None:
        print(f"STEPS: exact match found for volume={accepted_volume} kWh — using cache")
        df = matched_series
        source = f"cached (exact match={accepted_volume} kWh)"
    else:
        print(f"STEPS: no exact match for {accepted_volume} kWh — re-running BUC")
        df = await _run_buc_for_volume(dto, accepted_volume)
        source = f"re-computed BUC for exact volume={accepted_volume} kWh"

    timesteps = df.index.astype(str).tolist()

    payload = {
        "request_id": os.environ.get("AGENT_ID", "unknown"),
        "time_steps": timesteps,
        "eeg": df["soc_eeg"].tolist(),
        "wholesale": df["soc_wholesale"].tolist(),
        "community": df["soc_community"].tolist(),
        "home": df["soc_home"].tolist()
    }

    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "mas4te_restapi_key.yml")) as f:
        config = yaml.safe_load(f)

    r = requests.post(
        url="https://mas4te.nowum.fh-aachen.de/brp-api/power_request",
        auth=HTTPBasicAuth(username=config["api"]["username"], password=config["api"]["password"]),
        json=payload,
        params={
            "is_real_world_test": False,  # False = simulation mode (no real battery interaction)
                                          # True  = real-time mode (sends schedule to physical battery)
        },
    )

    print(r.status_code)
    try:
        print(r.json())
    except Exception:
        print("Response body:", r.text)

    dto.log_step(
        "publish_battery_schedule",
        "Sent the battery charging/discharging schedule to the API (buyer).",
        {
            "role": "buyer",
            "accepted_volume_kwh": accepted_volume,
            "schedule_source": source,
            "timesteps": len(timesteps),
        }
    )


async def _publish_schedule_seller(dto) -> None:
    """
    Sends SOC schedule to the physical battery via MQTT for sellers.
    Sellers own a physical battery — part of it is rented out to buyers (accepted_volume),
    the remaining capacity is used for their own demand/solar optimization.
    Only the own-use portion is scheduled here.
    """
    storage_size_kwh = dto.get("storage_size_kwh", 0)
    buc_charge_series = dto.get("buc_charge_series")

    if not buc_charge_series:
        print("STEPS: no buc_charge_series found, skipping")
        dto.log_step("publish_battery_schedule", "No SOC series found — step skipped.")
        return

    step = next((s for s in dto.trace if s["step"] == "market_clearing"), None)
    accepted_volume = step["metadata"].get("accepted_volume_kwh", 0) if step else 0

    own_volume = storage_size_kwh - accepted_volume
    print(f"STEPS: seller — total={storage_size_kwh} kWh, rented={accepted_volume} kWh, own use={own_volume} kWh")

    if own_volume <= 0:
        print("STEPS: entire battery is rented out, no own-use schedule to send")
        dto.log_step("publish_battery_schedule", "Entire battery rented out — no own-use schedule sent.")
        return

    matched_series = buc_charge_series.get(own_volume)
    if matched_series is not None:
        print(f"STEPS: exact match found for own_volume={own_volume} kWh — using cache")
        df = matched_series
        source = f"cached (exact match={own_volume} kWh)"
    else:
        print(f"STEPS: no exact match for own_volume={own_volume} kWh — re-running BUC")
        df = await _run_buc_for_volume(dto, own_volume)
        source = f"re-computed BUC for own_volume={own_volume} kWh"

    power_request = await soc_to_power_request({own_volume: df})

    mqtt_agent_battery = get_mqtt_agent_battery()
    mqtt_agent_battery.send_power_request_to_battery(power_request)

    print(f"STEPS: seller schedule sent via MQTT — {len(power_request['time_steps'])} timesteps")

    dto.log_step(
        "publish_battery_schedule",
        "Sent own-use battery schedule to physical battery via MQTT (seller).",
        {
            "role": "seller",
            "total_battery_kwh": storage_size_kwh,
            "rented_out_kwh": accepted_volume,
            "own_use_kwh": own_volume,
            "schedule_source": source,
            "timesteps": len(power_request["time_steps"]),
        }
    )


async def step_publish_battery_schedule(dto):
    """
    Routes to the correct schedule publishing function based on role.
    - Buyers: send SOC schedule to REST API (rented storage)
    - Sellers: send own-use SOC schedule to physical battery via MQTT
    """
    print("STEPS: step_publish_battery_schedule started")

    if dto.get("storage_size_kwh", 0) > 0:
        await _publish_schedule_seller(dto)
    else:
        await _publish_schedule_buyer(dto)

    return dto


# ---------------------------------------------------------------------------
# STEP MAP
# ---------------------------------------------------------------------------

STEP_MAP = {
    "market_open": [
        step1,
        step_retrieve_preferences,
        step_retrieve_profile,
        step_test_llm,
        step_market_open,
        step_retrieve_market_info,
        step_fc_demand,
        step_fc_solar,
        step_fc_prices,
        step_reason_buc_range,
        step_battery_utility_calculator,
        step_set_make_orderbook,
        step_publish_bid,
        step3,
    ],
    "market_clearing": [
        step4_retrieve_market_clearing_info,
        step_publish_battery_schedule,
    ],
}