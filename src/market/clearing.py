"""The clearing pipeline — runs when the market publishes its result.

Read this file top to bottom: it is the complete answer to "what does the agent
do once it knows what was accepted?"

  - Buyers rent virtual storage, so the schedule (state of charge over time per
    price source) goes to the BRP REST API.
  - Sellers own a physical battery. Only the part they keep for themselves
    (total minus what they rented out) gets scheduled, and it goes to the
    battery over MQTT.

The forecasts computed during bidding are reused here — run_clearing starts from
a copy of the last bidding run's data.
"""
import pandas as pd
import requests
from battery_utility_calculator import Storage, calculate_multiple_storage_worth
from requests.auth import HTTPBasicAuth

from config import DRY_RUN, POWER_REQUEST_URL, SOLVER, rest_api_credentials
from market.bidding import C_RATE, forecast_inputs
from market.pipeline import MarketContext, run_pipeline


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------
def soc_to_power_request(soc: pd.DataFrame) -> dict:
    """Turn a state-of-charge schedule into a battery power request.

    Sums the SOC across sources, then differentiates to get power (W) per step.
    """
    total_soc = soc.sum(axis=1)
    power_kw = (total_soc.diff() / 0.25).fillna(0)        # 0.25 h per step
    seconds = (total_soc.index - total_soc.index[0]).total_seconds().astype(int)
    return {"time_steps": seconds.tolist(), "power_rate_w": (power_kw * 1000).tolist()}


def charge_schedule_for(ctx: MarketContext, volume: float) -> pd.DataFrame | None:
    """The SOC schedule for one volume — from the bidding run, or recomputed.

    Sellers get theirs from bidding for free. Buyers never do: the by-location
    entry point the bidding step uses returns only a DataFrame and drops the
    charge timeseries, so their schedule is optimised again here, once, for the
    volume the market actually accepted.
    """
    cached = ctx.data.get("buc_charge_series", {}).get(volume)
    if cached is not None:
        return cached

    preferences = ctx.data.get("preferences", {})
    is_buyer = ctx.data.get("storage_size_kwh", 0) <= 0
    series = forecast_inputs(ctx)
    community = series.pop("community")
    my_location = ctx.data.get("location", "aachen").lower()

    result = calculate_multiple_storage_worth(
        baseline_storage=Storage(id=0, c_rate=C_RATE, volume=0),
        storages_to_calculate=[Storage(id=volume, c_rate=C_RATE, volume=volume)],
        community_market_prices={my_location: community},
        my_location=my_location,
        is_rented_storage=is_buyer,
        goal="max_green_energy" if preferences.get("trading_preference") == "Green" else "max_cashflow",
        solver=SOLVER,
        return_charge_timeseries=True,
        **series,
    )
    return result.get("storages_to_calc_charge_ts", {}).get(volume)


# --------------------------------------------------------------------------
# Steps
# --------------------------------------------------------------------------
def retrieve_clearing_info(ctx: MarketContext):
    orderbook = ctx.market_data.get("orderbook", [])
    role = "seller" if ctx.data.get("storage_size_kwh", 0) > 0 else "buyer"

    accepted = [o for o in orderbook if abs(o.get("accepted_volume", 0)) > 0]
    accepted_volume = sum(abs(o["accepted_volume"]) for o in accepted)
    clearing_price = orderbook[0]["accepted_price"] if orderbook else None

    ctx.data["accepted_volume_kwh"] = accepted_volume
    ctx.log(
        "market_clearing",
        "Received the market clearing result.",
        {
            "role": role,
            "bids_submitted": len(orderbook),
            "bids_accepted": len(accepted),
            "accepted_volume_kwh": round(accepted_volume, 2),
            "clearing_price_eur_kwh": round(clearing_price, 6) if clearing_price else None,
        },
    )


def publish_battery_schedule(ctx: MarketContext):
    if ctx.data.get("storage_size_kwh", 0) > 0:
        _publish_seller_schedule(ctx)
    else:
        _publish_buyer_schedule(ctx)


def _publish_buyer_schedule(ctx: MarketContext):
    """Buyer: send the rented-storage SOC schedule to the BRP REST API."""
    volume = ctx.data.get("accepted_volume_kwh", 0)
    if volume == 0:
        ctx.log("publish_battery_schedule", "No volume accepted — schedule not sent.")
        return

    soc = charge_schedule_for(ctx, volume)
    if soc is None:
        ctx.log("publish_battery_schedule", "No SOC schedule available — step skipped.")
        return

    payload = {
        "request_id": ctx.agent.agent_id,
        "time_steps": soc.index.astype(str).tolist(),
        "eeg": soc["soc_eeg"].tolist(),
        "wholesale": soc["soc_wholesale"].tolist(),
        "community": soc["soc_community"].tolist(),
        "home": soc["soc_home"].tolist(),
    }

    if DRY_RUN:
        ctx.log("publish_battery_schedule", "Dry run — buyer schedule computed but not sent.",
                {"role": "buyer", "accepted_volume_kwh": volume,
                 "timesteps": len(payload["time_steps"])})
        return

    username, password = rest_api_credentials()
    response = requests.post(
        POWER_REQUEST_URL,
        auth=HTTPBasicAuth(username, password),
        json=payload,
        params={"is_real_world_test": False},   # False = simulation, no physical battery
        timeout=60,
    )
    print(f"CLEARING: buyer schedule POST -> {response.status_code}")

    ctx.log("publish_battery_schedule", "Sent the rented-storage schedule to the API (buyer).",
            {"role": "buyer", "accepted_volume_kwh": volume, "timesteps": len(payload["time_steps"])})


def _publish_seller_schedule(ctx: MarketContext):
    """Seller: schedule only the own-use part of the battery, via MQTT."""
    total = ctx.data["storage_size_kwh"]
    rented = ctx.data.get("accepted_volume_kwh", 0)
    own_volume = total - rented

    if own_volume <= 0:
        ctx.log("publish_battery_schedule", "Entire battery rented out — no own-use schedule sent.")
        return

    soc = charge_schedule_for(ctx, own_volume)
    if soc is None:
        ctx.log("publish_battery_schedule", "No SOC schedule available — step skipped.")
        return

    power_request = soc_to_power_request(soc)
    if DRY_RUN:
        ctx.log("publish_battery_schedule", "Dry run — seller schedule computed but not sent.",
                {"role": "seller", "own_use_kwh": own_volume,
                 "timesteps": len(power_request["time_steps"])})
        return
    ctx.agent.battery_client.send_power_request(power_request)

    ctx.log("publish_battery_schedule", "Sent own-use battery schedule to the battery via MQTT (seller).",
            {"role": "seller", "total_battery_kwh": total, "rented_out_kwh": rented,
             "own_use_kwh": own_volume, "timesteps": len(power_request["time_steps"])})


CLEARING_STEPS = [
    retrieve_clearing_info,
    publish_battery_schedule,
]


def run_clearing(agent, market_data: dict) -> MarketContext:
    """Run the full clearing pipeline for one market-result event."""
    # Start from the matching bidding run, so the forecasts are already there.
    ctx = MarketContext(agent=agent, market_data=market_data, data=dict(agent.last_bidding_data))
    run_pipeline(ctx, CLEARING_STEPS, agent.pipeline_status)
    agent.clearing_traces.append(ctx.trace)
    return ctx
