"""The clearing pipeline — runs when the market clears.

Triggered by a ``market result`` MQTT message, this reads how much volume was
accepted and then sends the resulting battery schedule:

  - Buyers rent virtual storage, so the schedule (state-of-charge over time for
    each price source) goes to the BRP REST API.
  - Sellers own a physical battery; only the part they keep for themselves
    (total minus what they rented out) is scheduled, and it goes to the battery
    over MQTT.

The forecasts and charge schedules computed during bidding are reused here via
``agent.last_bidding_data`` (merged into this run's context).
"""
import pandas as pd
import requests
from requests.auth import HTTPBasicAuth

from battery_utility import Storage
import battery_utility
from config import POWER_REQUEST_URL, rest_api_credentials
from market.bidding import _to_series
from market.flow import MarketContext, run_blocking, run_pipeline


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------
async def soc_to_power_request(charge_by_volume: dict) -> dict:
    """Turn per-storage state-of-charge series into a battery power request.

    Sums the SOC across sources, differentiates to get power (W) per 15-min step.
    """
    total_soc = pd.concat(charge_by_volume.values(), axis=1).sum(axis=1)
    power_kw = (total_soc.diff() / 0.25).fillna(0)        # 0.25 h per step
    seconds = (total_soc.index - total_soc.index[0]).total_seconds().astype(int)
    return {
        "time_steps": seconds.tolist(),
        "power_rate_w": (power_kw * 1000).tolist(),
    }


async def _charge_schedule_for(ctx: MarketContext, volume: float) -> pd.DataFrame | None:
    """The SOC schedule for a given volume — from the bidding cache, or recomputed."""
    cached = ctx.data.get("buc_charge_series", {}).get(volume)
    if cached is not None:
        return cached

    preferences = ctx.data.get("preferences", {})
    is_buyer = ctx.data.get("storage_size_kwh", 0) <= 0
    demand = _to_series(ctx.data["demand_fc"])
    index = demand.index
    prices = ctx.data["prices_fc"]

    result = await run_blocking(
        battery_utility.storage_worth,
        baseline_storage=Storage(id=0, c_rate=0.2, volume=0),
        storages=[Storage(id=volume, c_rate=0.2, volume=volume)],
        demand=demand,
        solar=_to_series(ctx.data["solar_fc"]).reindex(index, method="nearest"),
        grid_prices=_to_series(prices.get("supplier")).reindex(index, method="nearest"),
        eeg_prices=_to_series(prices.get("eeg")).reindex(index, method="nearest"),
        community_prices=_to_series(prices.get("community")).reindex(index, method="nearest"),
        wholesale_prices=_to_series(prices.get("wholesale")).reindex(index, method="nearest"),
        my_location=ctx.data.get("location", "aachen"),
        is_buyer=is_buyer,
        trading_scope=preferences.get("trading_scope", "All"),
        goal="max_green_energy" if preferences.get("trading_preference") == "Green" else "max_cashflow",
        return_charge_timeseries=True,
    )
    return result.get("storages_to_calc_charge_ts", {}).get(volume)


# --------------------------------------------------------------------------
# Steps
# --------------------------------------------------------------------------
async def retrieve_clearing_info(ctx: MarketContext):
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


async def publish_battery_schedule(ctx: MarketContext):
    if ctx.data.get("storage_size_kwh", 0) > 0:
        await _publish_seller_schedule(ctx)
    else:
        await _publish_buyer_schedule(ctx)


async def _publish_buyer_schedule(ctx: MarketContext):
    """Buyer: send the rented-storage SOC schedule to the BRP REST API."""
    volume = ctx.data.get("accepted_volume_kwh", 0)
    if volume == 0:
        ctx.log("publish_battery_schedule", "No volume accepted — schedule not sent.")
        return

    df = await _charge_schedule_for(ctx, volume)
    if df is None:
        ctx.log("publish_battery_schedule", "No SOC schedule available — step skipped.")
        return

    payload = {
        "request_id": ctx.agent.agent_id,
        "time_steps": df.index.astype(str).tolist(),
        "eeg": df["soc_eeg"].tolist(),
        "wholesale": df["soc_wholesale"].tolist(),
        "community": df["soc_community"].tolist(),
        "home": df["soc_home"].tolist(),
    }

    username, password = rest_api_credentials()
    response = await run_blocking(
        requests.post,
        POWER_REQUEST_URL,
        auth=HTTPBasicAuth(username, password),
        json=payload,
        params={"is_real_world_test": False},   # False = simulation, no physical battery
    )
    print(f"CLEARING: buyer schedule POST -> {response.status_code}")

    ctx.log("publish_battery_schedule", "Sent the rented-storage schedule to the API (buyer).",
            {"role": "buyer", "accepted_volume_kwh": volume, "timesteps": len(payload["time_steps"])})


async def _publish_seller_schedule(ctx: MarketContext):
    """Seller: schedule only the own-use part of the battery, via MQTT."""
    total = ctx.data["storage_size_kwh"]
    rented = ctx.data.get("accepted_volume_kwh", 0)
    own_volume = total - rented

    if own_volume <= 0:
        ctx.log("publish_battery_schedule", "Entire battery rented out — no own-use schedule sent.")
        return

    df = await _charge_schedule_for(ctx, own_volume)
    if df is None:
        ctx.log("publish_battery_schedule", "No SOC schedule available — step skipped.")
        return

    power_request = await soc_to_power_request({own_volume: df})
    ctx.agent.battery_client.send_power_request(power_request)

    ctx.log("publish_battery_schedule", "Sent own-use battery schedule to the battery via MQTT (seller).",
            {"role": "seller", "total_battery_kwh": total, "rented_out_kwh": rented,
             "own_use_kwh": own_volume, "timesteps": len(power_request["time_steps"])})


CLEARING_STEPS = [
    retrieve_clearing_info,
    publish_battery_schedule,
]


async def run_clearing(agent, market_data: dict) -> MarketContext:
    """Run the full clearing pipeline for one market-result event."""
    # Reuse the forecasts and charge schedules from the matching bidding run.
    ctx = MarketContext(agent=agent, market_data=market_data, data=dict(agent.last_bidding_data))
    await run_pipeline(ctx, CLEARING_STEPS, agent.pipeline_status)
    agent.clearing_traces.append(ctx.trace)
    return ctx
