# core/pipeline/steps.py
import asyncio
from functools import partial
from concurrent.futures import ThreadPoolExecutor

from core.llm.tools.registry import tool_registry
from core.main_context import GLOBAL_PROFILE_ID
from core.main_context import get_mqtt_agent

import pandas as pd
from datetime import datetime

from core.llm.tools.chronos_tool import forecast_timeseries_from_csv
from api.services.prosumer.prosumer_service import ProsumerService

from core.domain.chat_session import SolarChatSession
from core.main_context import get_llm


# ---------------------------------------------------------------------------
# Bounded thread pool — limits how many CPU-heavy calls run simultaneously.
# Without this, launching too many threads at once causes CPU contention and
# actually makes everything slower. Tune max_workers to your core count.
# ---------------------------------------------------------------------------
THREAD_POOL = ThreadPoolExecutor(max_workers=1)


async def run_blocking(fn, *args, **kwargs):
    """
    Offloads a synchronous, blocking function to a bounded thread-pool worker.
    The event loop remains free to handle other requests (e.g. chatbot)
    while the function runs in a separate thread.

    Usage:
        result = await run_blocking(some_sync_fn, arg1, arg2, kwarg=value)
    """
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(THREAD_POOL, partial(fn, *args, **kwargs))


def retrieve_step_map():
    return STEP_MAP


# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------

def _to_1d(x):
    """Coerce DataFrames, arrays, or lists to a flat pandas Series."""
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

    # Strip timezone so downstream code stays compatible
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

async def step1(data):
    data["step1"] = "done"
    print("STEPS: Step 1 completed")
    return data

async def step_test_llm(data):
    """Simple test step to verify the LLM is accessible from the pipeline."""
    from core.main_context import get_llm
    from core.domain.chat_session import SolarChatSession

    llm = get_llm()
    if llm is None:
        print("STEPS: step_test_llm — no LLM found, skipping")
        return data

    print("STEPS: step_test_llm — LLM found, sending test message...")

    session = SolarChatSession(llm=llm, prompt="You are a helpful assistant.")
    response = await run_blocking(session.process_message, "Say hello in one sentence.")

    print(f"STEPS: step_test_llm — response: {response}")
    data["llm_test_response"] = response
    return data



async def step_retrieve_preferences(data):
    # ProsumerService.get_preferences() is a lightweight DB/config read.
    # If it ever becomes slow, wrap it with run_blocking too.
    service = ProsumerService()
    preferences = service.get_preferences()
    data["preferences"] = preferences
    if data.get("storage_size_kwh", 0) > 0:
        data["battery_tradeable_pct"] = preferences.get("battery_tradeable_pct", 50)
    # data["battery_tradeable_pct"] = preferences.get("battery_tradeable_pct", 50)

    print("STEPS: preferences retrieved:", preferences)
    return data


async def step_retrieve_profile(data):
    tool_get_profile = next(
        t for t in tool_registry.tools if t.__name__ == "get_profile_metadata"
    )
    # Synchronous tool call — offload so the loop stays free
    result_profile = await run_blocking(tool_get_profile, GLOBAL_PROFILE_ID)
    print("result profile", result_profile)
    data["storage_size_kwh"] = result_profile.get("battery_size_kwh", 0.0)
    print(data["storage_size_kwh"])
    return data


async def step_market_open(data):
    print("PIPELINE: Market opened step triggered!")
    print("market data", data["market_data"])
    data["market_open_processed"] = True
    return data


async def step_retrieve_market_info(data):
    market_info = data["market_data"]
    products = market_info.get("products", [])
    starts, ends = [], []
    for p in products:
        if "start_time" in p and "end_time" in p:
            starts.append(pd.to_datetime(p["start_time"]))
            ends.append(pd.to_datetime(p["end_time"]))

    # Only use the first product for now
    data["market_window"] = {"start": starts[0], "end": ends[0]}
    print("market window", data["market_window"])
    return data


async def step_fc_demand(data):
    """
    Forecast demand using Chronos.
    run_blocking offloads the CPU-heavy inference to a worker thread,
    keeping the event loop (and chatbot) responsive while it runs.
    """
    print("STEPS: step_fc_demand started")
    start = pd.to_datetime(data["market_window"]["start"])
    end = pd.to_datetime(data["market_window"]["end"])

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

    print("STEPS: Chronos demand returned, length:", len(demand_fc["median"]))
    timestamps = pd.to_datetime(list(demand_fc["timestamps"]), errors="raise")
    data["demand_fc"] = pd.Series(demand_fc["median"], index=timestamps)
    print("STEPS: demand forecast\n", data["demand_fc"])
    return data


async def step_fc_solar(data):
    """
    Forecast solar generation using Chronos.
    Same pattern as step_fc_demand — offloaded to thread pool.
    """
    print("STEPS: step_fc_solar started")
    start = pd.to_datetime(data["market_window"]["start"])
    end = pd.to_datetime(data["market_window"]["end"])

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

    print("STEPS: Chronos solar returned, length:", len(solar_fc["median"]))
    timestamps = pd.to_datetime(list(solar_fc["timestamps"]), errors="raise")
    data["solar_fc"] = pd.Series(solar_fc["median"], index=timestamps)
    print("STEPS: solar forecast\n", data["solar_fc"])
    return data


async def step_fc_prices(data):
    """
    Forecast all price columns using Chronos — sequentially.

    Running these concurrently caused CPU contention (Chronos is heavy).
    Sequential is slower wall-clock but doesn't thrash the CPU, and the
    event loop stays free between each awaited call so the chatbot
    remains responsive throughout.
    """
    print("STEPS: step_fc_prices started")
    start = pd.to_datetime(data["market_window"]["start"])
    end = pd.to_datetime(data["market_window"]["end"])

    price_csv = "data/profile_data/prices.csv"
    df = pd.read_csv(price_csv)
    if df.columns[0] == "Unnamed: 0":
        df = df.drop(columns=df.columns[0])

    price_columns = [c for c in df.columns if c != "datetime"]
    print("STEPS: price columns to forecast:", price_columns)

    prices_fc = {}
    for col in price_columns:
        print(f"STEPS: forecasting price column '{col}'")
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
        print(f"STEPS: Chronos returned {len(result['median'])} points for '{col}'")
        timestamps = pd.to_datetime(result["timestamps"], errors="raise")
        prices_fc[col] = pd.Series(result["median"], index=timestamps)

    data["prices_fc"] = prices_fc

    print("STEPS: all price forecasts done")
    for k, v in data["prices_fc"].items():
        print(k, v.head())

    return data

async def step_reason_buc_range_buy(data):
    """
    Ask the LLM to reason about what volume range to run the BUC for.
 
    Uses a fresh isolated session — completely separate from the chatbot's
    conversation history. The LLM gets demand forecast summary, trading
    preference, and market window, and returns a min/max volume range + reasoning.
 
    Falls back to range(1, 10) if the LLM call fails or returns invalid JSON.
    """
    print("STEPS: step_reason_buc_range started")
 
    llm = get_llm()
    if llm is None:
        print("STEPS: no LLM available, using fallback range 1–10")
        data["buc_min_volume"] = 1
        data["buc_max_volume"] = 10
        return data
 
    # Summarise demand forecast so we don't dump a huge series into the prompt
    demand_fc = data.get("demand_fc")
    if demand_fc is not None and len(demand_fc) > 0:
        demand_summary = (
            f"min={demand_fc.min():.2f} kWh, "
            f"max={demand_fc.max():.2f} kWh, "
            f"mean={demand_fc.mean():.2f} kWh "
            f"over {len(demand_fc)} time steps"
        )
    else:
        demand_summary = "not available"
 
    preferences = data.get("preferences", {})
    trading_preference = preferences.get("trading_preference", "unknown")
    market_window = data.get("market_window", {})
 
    prompt = f"""You are an energy trading coach helping a buyer decide how much 
    storage capacity to bid for in a local energy market. Always respond in English AND ONLY ENGLISH. 

    The buyer does NOT own a battery — they are renting storage capacity from the community.

    Trading preferences explained:
    - "Profit": minimize electricity costs, bid only what is economically worth it
    - "Green Energy": maximize use of renewable energy, willing to rent more storage 
    even if not the most cost-efficient choice

    Available information:
    - Demand forecast: {demand_summary}
    - Trading preference: {trading_preference}
    - Market window: start={market_window.get('start')}, end={market_window.get('end')}

    Based on this, decide a sensible minimum and maximum volume range (in kWh) to run 
    the BUC for. Minimum must be at least 1 kWh. If you choose to not start at 1 kWh, explain why. 

    Respond with JSON only:
    {{"min_volume": <integer>, "max_volume": <integer>, "reasoning": "<brief explanation>"}}"""
    
    
    # Fresh isolated session — does not affect chatbot history
    session = SolarChatSession(
        llm=llm,
        prompt="You are an energy trading assistant. Respond only with valid JSON when asked."
    )
 
    print("STEPS: asking LLM to reason about BUC volume range...")
    try:
        import json as _json
        response = await run_blocking(session.process_message, prompt)
        print(f"STEPS: LLM reasoning response:\n{response}\n")
 
        # Strip markdown code fences if present
        clean = response.strip().replace("```json", "").replace("```", "").strip()
        decision = _json.loads(clean)
 
        min_vol = max(1, int(decision["min_volume"]))
        max_vol = max(min_vol, int(decision["max_volume"]))
 
        data["buc_min_volume"] = min_vol
        data["buc_max_volume"] = max_vol
        print(f"STEPS: agent decided BUC range: {min_vol}–{max_vol} kWh")
        print(f"STEPS: reasoning: {decision.get('reasoning', '')}")
 
    except Exception as e:
        print(f"STEPS: reasoning step failed ({e}), using fallback range 1–10")
        data["buc_min_volume"] = 1
        data["buc_max_volume"] = 10
    # print(q)
    return data

async def step_battery_utility_calculator(data):
    """
    Run the Battery Utility Calculator for every storage volume from 1 kWh
    up to the prosumer's actual battery size percentage allowed.
    """
    print("STEPS: step_battery_utility_calculator started")

    # Prepare inputs
    demand_series    = _to_1d(data.get("demand_fc"))
    solar_series     = _to_1d(data.get("solar_fc"))
    grid_prices      = _to_1d(data.get("prices_fc", {}).get("supplier"))
    eeg_prices       = _to_1d(data.get("prices_fc", {}).get("eeg"))
    community_prices = _to_1d(data.get("prices_fc", {}).get("community"))
    wholesale_prices = _to_1d(data.get("prices_fc", {}).get("wholesale"))

    buc_tool = next(
        t for t in tool_registry.tools if t.__name__ == "battery_utility_calculator"
    )

    common_kwargs = dict(
        demand_series=demand_series,
        solar_series=solar_series,
        grid_prices=grid_prices,
        eeg_prices=eeg_prices,
        community_prices=community_prices,
        wholesale_prices=wholesale_prices,
    )

    if data.get("storage_size_kwh", 0) > 0:  # seller
        tradeable_pct = data.get("battery_tradeable_pct", 50)  # fallback to 100%
        storage_size_kwh = int(data["storage_size_kwh"] * (tradeable_pct / 100))
        print('full storage: ', data["storage_size_kwh"], "% : ", tradeable_pct / 100, "trade kwh: ", storage_size_kwh)
        volumes = range(1, storage_size_kwh + 1)
        goal = data["preferences"].get("goal", "max_cashflow")

    else:  # buyer — ask LLM to reason about volume range first
        trading_preference = data.get("preferences", {}).get("trading_preference", "Profit")
        goal = "max_green_energy" if trading_preference == "Green Energy" else "max_cashflow"
        print(f"STEPS: using goal '{goal}' based on trading preference '{trading_preference}'")

        # Inline LLM reasoning for volume range (buyers only)
        data = await step_reason_buc_range_buy(data)

        min_volume = data.get("buc_min_volume", 1)
        max_volume = data.get("buc_max_volume", 10)
        volumes = range(min_volume, max_volume + 1)
        print(f"STEPS: running BUC for volumes {min_volume}–{max_volume} kWh | goal={goal}")

    buc_results = {}
    for volume in volumes:
        result = await run_blocking(
            buc_tool,
            storage_size_kwh=volume,
            goal=goal,
            **common_kwargs,
        )
        buc_results[volume] = result

    print('buc_results ', buc_results)

    # print('buc results: ', buc_results)
    def _print_buc_results(buc_results: dict):
        print("\n" + "="*60)
        print("BUC RESULTS SUMMARY")
        print("="*60)
        print(f"{'Volume (kWh)':<15} {'Worth (€)':<15} {'Bid Volume':<15} {'Marginal Price (€)':<20} {'€/kWh':<10}")
        print("-"*60)
        for volume, result in buc_results.items():
            worth = result["single_worth"]
            curve = result["bidding_curve"]
            bid_volume = curve["volume"][0]
            marginal_price = curve["marginal_price"][0]
            price_per_kwh = curve["marginal_price_per_kwh"][0]
            print(f"{volume:<15} {worth:<15.4f} {bid_volume:<15.2f} {marginal_price:<20.4f} {price_per_kwh:<10.4f}")
        print("="*60 + "\n")

    _print_buc_results(buc_results=buc_results)
    data["buc_results"] = buc_results
    print("STEPS: END OF BUC")
    return data

async def step_set_make_orderbook(data):
    print("STEPS: ENTER BUC STEP")

    data["bid_id"] = 0 if data.get("bid_id") is None else data["bid_id"] + 1

    buc_results = data.get("buc_results")

    if not buc_results:
        print("STEPS: NO BUC RESULTS")
        data["orderbook"] = []
        return data

    first_key = next(iter(buc_results))
    result = buc_results[first_key]

    print("STEPS: selected volume key:", first_key)

    curve = result.get("bidding_curve", {})

    volume_dict = curve.get("volume", {})
    price_dict = curve.get("marginal_price_per_kwh", {})

    if not volume_dict or not price_dict:
        print("STEPS: missing curve data")
        data["orderbook"] = []
        return data

    v = next(iter(volume_dict.values()))
    p = next(iter(price_dict.values()))

    print("STEPS: extracted v:", v)
    print("STEPS: extracted p:", p)

    data["orderbook"] = [
        {
            "bid_id": data["bid_id"],
            "volume": v,
            "price": p
        }
    ]

    print("STEPS: FINAL ORDERBOOK:", data["orderbook"])

    return data

async def step_publish_bid(data):
    print("STEPS: step_publish_bid started")

    # ensure orderbook exists
    orderbook = data.get("orderbook")

    if not orderbook:
        print("STEPS: no orderbook to publish")
        return data

    print("STEPS: publishing orderbook:", orderbook)

    mqtt_agent = get_mqtt_agent()
    mqtt_agent.send_orderbook_to_market(orderbook)

    print("STEPS: bid published successfully")
    return data


# ---------------------------------------------------------------------------
# STEPS — debug / utility
# ---------------------------------------------------------------------------

async def time_tool_step(data):
    print("Tools in registry:")
    for t in tool_registry.tools:
        print("-", t.__name__)

    tool = next(t for t in tool_registry.tools if t.__name__ == "get_current_time")
    result = await run_blocking(tool)
    data["current_time"] = result["current_time"]
    return data


async def step2(data):
    print("Step 2 sees current_time:", data.get("current_time"))
    data["step2"] = "done"
    print("STEPS: Step 2 completed")
    return data


async def step3(data):
    data["step3"] = "done"
    print("STEPS: All steps completed")
    return data


# ---------------------------------------------------------------------------
# STEPS — market_clearing sequence
# ---------------------------------------------------------------------------

async def step4_retrieve_market_clearing_info(data):
    print("market clearing info:", data.get("market_data"))
    print("STEPS: Step 4 completed - in market clearing")
    return data


# ---------------------------------------------------------------------------
# STEP MAP
# ---------------------------------------------------------------------------

STEP_MAP = {
    "market_open": [
        step1,
        step_retrieve_preferences,
        step_retrieve_profile,   # uncomment if needed
        # step_test_llm,
        # time_tool_step,
        # step2,
        step_market_open,
        step_retrieve_market_info,
        step_fc_demand,           
        step_fc_solar,            
        step_fc_prices,     
        # step_reason_buc_range_buy,      
        step_battery_utility_calculator,
        step_set_make_orderbook,
        step_publish_bid,        # uncomment when ready
        step3,
    ],
    "market_clearing": [
        step4_retrieve_market_clearing_info,
    ],
}

