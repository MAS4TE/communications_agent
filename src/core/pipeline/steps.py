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

from battery_utility_calculator import calculate_bidding_curve

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


async def soc_to_power_request(buc_soc_series: dict) -> dict:
    """
    Sum SOC series across all volumes and convert to a power request.
    Returns a dict with time_steps (seconds from start) and power_rate_w.
    """
    # Sum all SOC series into one
    all_socs = pd.concat(buc_soc_series.values(), axis=1)
    soc_total = all_socs.sum(axis=1)

    dt_hours = 0.25  # 15-min timesteps
    power_kw = soc_total.diff() / dt_hours
    power_kw = power_kw.fillna(0)
    power_w = power_kw * 1000

    time_steps_s = (soc_total.index - soc_total.index[0]).total_seconds().astype(int)

    return {
        "time_steps": time_steps_s.tolist(),
        "power_rate_w": power_w.tolist(),
    }

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
    Run the Battery Utility Calculator (BUC) across all tradeable volumes and
    produce a bidding curve for market submission.

    --- Conceptual overview ---

    Worth is always defined as: worth = cost(baseline) - cost(candidate)
    A positive worth means the candidate storage makes the prosumer better off.

    The baseline differs by role:

      SELLER (has a real battery, renting out part of it):
        - Baseline  = full battery used entirely for self-consumption
        - Candidate = full battery minus N kWh (what they keep after renting out N)
        - Worth     = how much worse off they are by giving away N kWh
                    = the minimum price they should accept for N kWh
        - Loop      : N goes from 1 up to max_tradeable kWh (in steps of 1)
        - Curve     : seller side — sorted descending by volume (highest value first)

      BUYER (no battery, paying to use virtual storage):
        - Baseline  = no storage (0 kWh), buying all energy from the grid
        - Candidate = N kWh of virtual storage
        - Worth     = energy cost saving from having N kWh available
                    = the maximum price they should be willing to pay for N kWh
        - Loop      : N goes from min_volume to max_volume (LLM-reasoned range)
        - Curve     : buyer side — sorted ascending by volume (cheapest first)

    --- Bidding curve construction ---

    Worth values collected across volumes are cumulative (each is vs the same baseline).
    calculate_bidding_curve() diffs consecutive worth values to get the marginal price
    per 1 kWh step, i.e.:

        marginal_price(step N) = worth(N kWh) - worth(N-1 kWh)

    This marginal price per kWh is the actual bid price submitted to the market.

    Args:
        data (dict): Pipeline data dict. Expected keys:
            'demand_fc'              : demand forecast timeseries
            'solar_fc'               : solar generation forecast timeseries
            'prices_fc'              : dict with 'supplier', 'eeg', 'community', 'wholesale'
            'storage_size_kwh'       : full battery size in kWh (sellers only, >0)
            'battery_tradeable_pct'  : percentage of battery available to trade (sellers)
            'preferences'            : dict with 'goal' (sellers) or 'trading_preference' (buyers)
            'buc_min_volume'         : min volume in kWh to evaluate (buyers, set by LLM)
            'buc_max_volume'         : max volume in kWh to evaluate (buyers, set by LLM)

    Returns:
        dict: Updated data dict with added keys:
            'bidding_curve'  : pd.DataFrame with columns
                               [volume, cumulative_volume, marginal_price, marginal_price_per_kwh]
            'buc_soc_series' : dict mapping volume (int) → SOC timeseries (pd.Series),
                               retained for future MQTT battery scheduling
    """
    print("=" * 60)
    print("STEPS: step_battery_utility_calculator started")
    print("=" * 60)

    # --- Prepare input timeseries ---
    demand_series    = _to_1d(data.get("demand_fc"))
    solar_series     = _to_1d(data.get("solar_fc"))
    grid_prices      = _to_1d(data.get("prices_fc", {}).get("supplier"))
    eeg_prices       = _to_1d(data.get("prices_fc", {}).get("eeg"))
    community_prices = _to_1d(data.get("prices_fc", {}).get("community"))
    wholesale_prices = _to_1d(data.get("prices_fc", {}).get("wholesale"))

    buc_tool = next(
        t for t in tool_registry.tools if t.__name__ == "battery_utility_calculator"
    )

    # These kwargs are the same for every BUC call — only baseline/candidate change per volume
    common_kwargs = dict(
        demand_series=demand_series,
        solar_series=solar_series,
        grid_prices=grid_prices,
        eeg_prices=eeg_prices,
        community_prices=community_prices,
        wholesale_prices=wholesale_prices,
    )

    # --- Determine role, volumes, and baseline ---
    if data.get("storage_size_kwh", 0) > 0:  # seller
        trading_preference = data.get("preferences", {}).get("trading_preference", "Profit")
        full_battery_kwh = data["storage_size_kwh"]
        tradeable_pct = data.get("preferences", {}).get("battery_tradeable_pct", 50)
        max_tradeable    = int(full_battery_kwh * (tradeable_pct / 100))
        goal               = "max_green_energy" if trading_preference == "Green Energy" else "max_cashflow"
        side             = "seller"

        # Each step N: seller offers N kWh, keeps (full_battery - N) for themselves
        volumes = range(1, max_tradeable + 1)

        print(f"  Role             : SELLER")
        print(f"  Full battery     : {full_battery_kwh} kWh")
        print(f"  Tradeable        : {tradeable_pct}%  →  max {max_tradeable} kWh offered")
        print(f"  Baseline         : {full_battery_kwh} kWh  (full battery, self-consuming only)")
        print(f"  Candidate range  : {full_battery_kwh - max_tradeable} – {full_battery_kwh - 1} kWh kept")
        print(f"  Goal             : {goal}")
        print(f"  Volumes to test  : 1 – {max_tradeable} kWh offered ({max_tradeable} steps)")
        print('full storage: ', full_battery_kwh, "% : ", tradeable_pct / 100, "trade kwh: ", max_tradeable)

        # print(q)

    else:  # buyer
        trading_preference = data.get("preferences", {}).get("trading_preference", "Profit")
        goal               = "max_green_energy" if trading_preference == "Green Energy" else "max_cashflow"
        side               = "buyer"

        print(f"  Role             : BUYER")
        print(f"  Trading pref     : {trading_preference}  →  goal = {goal}")
        print(f"  Baseline         : 0 kWh  (no storage)")
        print(f"STEPS: using goal '{goal}' based on trading preference '{trading_preference}'")

        # LLM-reasoned volume range — buyer has no battery so we estimate
        # how much virtual storage would be useful given their demand/solar profile
        data       = await step_reason_buc_range_buy(data)
        min_volume = data.get("buc_min_volume", 1)
        max_volume = data.get("buc_max_volume", 10)
        volumes    = range(min_volume, max_volume + 1)

        print(f"  Candidate range  : {min_volume} – {max_volume} kWh")
        print(f"  Volumes to test  : {min_volume} – {max_volume} kWh ({max_volume - min_volume + 1} steps)")
        print(f"STEPS: running BUC for volumes {min_volume}–{max_volume} kWh | goal={goal}")

        # print(q)

    print()

    # --- BUC loop: one call per volume step ---
    buc_results    = {}  # volume (int) → {"worth": float, "storage_to_calc_charge_ts": df}
    buc_soc_series = {}  # volume (int) → SOC timeseries (pd.Series), retained for MQTT scheduling

    for volume in volumes:
        if side == "seller":
            # Seller's baseline is always their full battery.
            # Candidate is what remains after renting out `volume` kWh.
            baseline_kwh  = full_battery_kwh
            candidate_kwh = full_battery_kwh - volume
        else:
            # Buyer's baseline is always no storage.
            # Candidate is the virtual storage they are considering buying.
            baseline_kwh  = 0
            candidate_kwh = volume

        result = await run_blocking(
            buc_tool,
            storage_size_kwh=candidate_kwh,
            baseline_storage_kwh=baseline_kwh,
            goal=goal,
            return_charge_timeseries=True,  # needed for SOC tracking and future MQTT scheduling
            **common_kwargs,
        )
        buc_results[volume] = result

        # Extract and store SOC timeseries for this volume
        df = result["storage_to_calc_charge_ts"]
        df["soc_total"] = df.sum(axis=1)  # sum across charge columns to get total SOC
        buc_soc_series[volume] = df["soc_total"]

        worth       = result["worth"]
        soc_nonzero = (df["soc_total"] != 0).sum()
        print(
            f"  [BUC] offer {volume:>3} kWh  |  "
            f"candidate={candidate_kwh} kWh  baseline={baseline_kwh} kWh  |  "
            f"worth = {worth:+.4f} EUR  |  "
            f"SOC non-zero timesteps: {soc_nonzero}/{len(df)}"
        )

    # Original SOC diagnostic prints — useful for catching all-zero SOC issues
    # which indicate the optimizer is not using the storage at all
    print('buc_results ', buc_results)
    print(buc_soc_series)
    print("STEPS: buc_soc_series sample:")
    for vol, soc in buc_soc_series.items():
        print(f"  volume {vol} kWh — {len(soc)} timesteps, head: {soc.head()}")
        if buc_soc_series[vol].eq(0).all():
            print(f"  WARNING: volume {vol} kWh — soc_total is ALL ZEROS")
        else:
            print(f"  OK: volume {vol} kWh — soc_total has non-zero values")

    print()

    # --- Build bidding curve from collected worth values ---
    # Worth values are cumulative (each volume is compared to the same baseline).
    # calculate_bidding_curve diffs them to produce a marginal price per 1 kWh step,
    # which is the actual price submitted per slot in the market bid.
    print("STEPS: building bidding curve ...")

    # The baseline row (volume=0, worth=0) is required by calculate_bidding_curve
    # as the anchor point for the first diff.
    rows = [{"volume": 0, "worth": 0.0}]
    for volume, result in buc_results.items():
        rows.append({"volume": volume, "worth": result["worth"]})

    volumes_worth_df = pd.DataFrame(rows)

    bidding_curve = calculate_bidding_curve(
        volumes_worth=volumes_worth_df,
        buy_or_sell_side=side,
    )

    print()
    print(f"  {'Step':>4}  {'Volume (kWh)':>12}  {'Cumul. (kWh)':>12}  {'Marginal (EUR)':>14}  {'EUR/kWh':>10}")
    print(f"  {'-'*4}  {'-'*12}  {'-'*12}  {'-'*14}  {'-'*10}")
    for i, row in bidding_curve.iterrows():
        print(
            f"  {i+1:>4}  "
            f"{row['volume']:>12.1f}  "
            f"{row['cumulative_volume']:>12.1f}  "
            f"{row['marginal_price']:>14.4f}  "
            f"{row['marginal_price_per_kwh']:>10.4f}"
        )

    print()
    print(
        f"  → {len(bidding_curve)} bid steps | "
        f"total volume: {bidding_curve['cumulative_volume'].max():.1f} kWh | "
        f"price range: {bidding_curve['marginal_price_per_kwh'].min():.4f} – "
        f"{bidding_curve['marginal_price_per_kwh'].max():.4f} EUR/kWh"
    )
    print("=" * 60)

    data["bidding_curve"]  = bidding_curve
    data["buc_soc_series"] = buc_soc_series

    return data


async def step_set_make_orderbook(data):
    """
    Build the orderbook from the bidding curve produced by step_battery_utility_calculator.

    Each row in the bidding curve becomes one order in the orderbook, representing
    one 1-kWh slot at its marginal price. This gives a stepped bid where each
    additional kWh is priced at its marginal value:

      Sellers: bids are sorted highest price first (most valuable kWh first)
      Buyers:  bids are sorted lowest price first (cheapest kWh first)

    The orderbook is what gets submitted to the market.
    """
    print("STEPS: ENTER MAKE ORDERBOOK STEP")

    # Increment bid_id for this round
    data["bid_id"] = 0 if data.get("bid_id") is None else data["bid_id"] + 1

    bidding_curve = data.get("bidding_curve")

    if bidding_curve is None or bidding_curve.empty:
        print("STEPS: NO BIDDING CURVE FOUND — orderbook will be empty")
        data["orderbook"] = []
        return data

    print(f"STEPS: building orderbook from {len(bidding_curve)} curve steps ...")

    orderbook = []
    for i, row in bidding_curve.iterrows():
        order = {
            "bid_id":  f"{data['bid_id']}_{i + 1}",    # unique id per bid
            "slot":    i + 1,                          # 1-based step index
            "volume":  row["volume"],                  # always 1 kWh per step
            "price":   row["marginal_price_per_kwh"],  # EUR/kWh for this slot
        }
        orderbook.append(order)
        print(f"  slot {order['slot']:>3}  |  volume={order['volume']:.1f} kWh  |  price={order['price']:.4f} EUR/kWh")

    data["orderbook"] = orderbook

    print(f"STEPS: FINAL ORDERBOOK — {len(orderbook)} bids | "
          f"total volume: {sum(o['volume'] for o in orderbook):.1f} kWh | "
          f"price range: {min(o['price'] for o in orderbook):.4f} – "
          f"{max(o['price'] for o in orderbook):.4f} EUR/kWh")

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

async def step_publish_battery_schedule(data):
    print("STEPS: step_publish_battery_schedule started")

    if data.get("storage_size_kwh", 0) <=0:
        print('STEPS: not a seller, skipping battery schedule publishing')
        # maybe change this after discussion with C on when to calculate this and where to actually send it
        return data

    buc_soc_series = data.get("buc_soc_series")
    if not buc_soc_series:
        print("STEPS: no buc_soc_series found, skipping")
        return data

    power_request = await soc_to_power_request(buc_soc_series)
    print(f"STEPS: power request — {len(power_request['time_steps'])} timesteps, first power: {power_request['power_rate_w'][0]:.2f} W")

    mqtt_agent = get_mqtt_agent()
    mqtt_agent.send_power_request_to_battery(power_request)

    print("STEPS: battery schedule published successfully")
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
        step_publish_bid,        
        step_publish_battery_schedule,
        step3,
    ],
    "market_clearing": [
        step4_retrieve_market_clearing_info,
    ],
}

