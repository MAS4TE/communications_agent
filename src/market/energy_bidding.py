"""The energy-market pipelines — run when the community energy market opens or clears.

ASSUME can run a community energy-only market (CommunityEOM) next to the battery
market, on its own topics (mas4te/community_eom/...). It is switched off there
(ENABLE_COMMUNITY_EOM in mas4te/simulation.py); these pipelines make sure the
agent is ready when it is switched on.

    profile -> preferences -> open delivery periods (e.g. 96 quarter hours)
        -> forecast demand, solar and prices
        -> one bid per period: sell the PV surplus, buy the deficit
        -> publish

The bids are deliberately simple: what the household would otherwise get or pay.
A surplus is offered at the feed-in tariff (the least it accepts, since it could
feed in instead), a deficit is bid at the supplier price (the most it pays, since
it could buy from the supplier instead). The home battery is not used here.

Steps are reused from bidding.py where they fit; see that file for the details.
"""
import logging

import pandas as pd

from config import DRY_RUN
from market.bidding import (
    _to_series,
    forecast_demand,
    forecast_prices,
    forecast_solar,
    retrieve_preferences,
    retrieve_profile,
)
from market.pipeline import MarketContext, run_pipeline

log = logging.getLogger("energy_bidding")

# bids below this volume (kW) are not worth sending
MIN_VOLUME_KW = 0.01


def retrieve_energy_products(ctx: MarketContext):
    """All open delivery periods; the forecasts cover them from first start to last end."""
    products = []
    for product in ctx.market_data.get("products", []):
        if "start_time" not in product or "end_time" not in product:
            continue
        start = pd.to_datetime(product["start_time"])
        end = pd.to_datetime(product["end_time"])
        if start.tzinfo is not None:
            start, end = start.tz_convert(None), end.tz_convert(None)
        products.append({"start": start, "end": end, "start_time": product["start_time"]})
    if not products:
        raise ValueError(f"market_open message carries no products: {ctx.market_data!r}")

    ctx.data["products"] = products
    ctx.data["window"] = {"start": min(p["start"] for p in products),
                          "end": max(p["end"] for p in products)}
    ctx.log("retrieve_energy_products", "Extracted the open delivery periods of the energy market.",
            {"market_id": ctx.market_data.get("market_id"), "periods": len(products),
             "window_start": str(ctx.data["window"]["start"]),
             "window_end": str(ctx.data["window"]["end"])})


def _period_mean(series, start, end) -> float:
    """Mean of a forecast over one delivery period, nearest value if none falls inside."""
    series = _to_series(series)
    if series is None or len(series) == 0:
        return 0.0
    inside = series[(series.index >= start) & (series.index < end)]
    if len(inside):
        return float(inside.mean())
    return float(series.iloc[series.index.get_indexer([start], method="nearest")[0]])


def make_energy_orderbook(ctx: MarketContext):
    """One bid per delivery period: sell the PV surplus or buy the deficit."""
    prices = ctx.data["prices_fc"]
    blockchain_address = getattr(ctx.agent, "blockchain_address", None)

    orderbook = []
    for product in ctx.data["products"]:
        start, end = product["start"], product["end"]
        net_kw = (_period_mean(ctx.data["solar_fc"], start, end)
                  - _period_mean(ctx.data["demand_fc"], start, end))
        if abs(net_kw) < MIN_VOLUME_KW:
            continue
        if net_kw > 0:
            side, price = "sell", _period_mean(prices.get("eeg"), start, end)
        else:
            side, price = "buy", _period_mean(prices.get("supplier"), start, end)

        bid = {
            "bid_id": f"{ctx.agent.profile_id}_{ctx.agent.next_bid_id()}",
            "start_time": product["start_time"],
            "side": side,
            "quantity": round(abs(net_kw), 3),
            "price": round(price, 4),
        }
        if blockchain_address:
            bid["blockchain_address"] = blockchain_address
        orderbook.append(bid)

    ctx.data["orderbook"] = orderbook
    sold = sum(b["quantity"] for b in orderbook if b["side"] == "sell")
    bought = sum(b["quantity"] for b in orderbook if b["side"] == "buy")
    ctx.log("make_energy_orderbook",
            "Offered the PV surplus at the feed-in tariff and bid for the deficit at the supplier price.",
            {"num_orders": len(orderbook), "sell_kw_total": round(sold, 2),
             "buy_kw_total": round(bought, 2),
             "blockchain_address": bool(blockchain_address)})


def publish_energy_bid(ctx: MarketContext):
    orderbook = ctx.data.get("orderbook")
    if not orderbook:
        ctx.log("publish_energy_bid", "No orderbook to publish — step skipped.")
        return
    if DRY_RUN:
        ctx.log("publish_energy_bid", "Dry run — orderbook built but not published.",
                {"num_orders": len(orderbook)})
        return
    ctx.agent.market_client.send_energy_orderbook(orderbook)
    ctx.log("publish_energy_bid", "Submitted the orderbook to the energy market via MQTT.",
            {"num_orders_sent": len(orderbook)})


ENERGY_BIDDING_STEPS = [
    retrieve_profile,
    retrieve_preferences,
    retrieve_energy_products,
    forecast_demand,
    forecast_solar,
    forecast_prices,
    make_energy_orderbook,
    publish_energy_bid,
]


def record_energy_result(ctx: MarketContext):
    """Keep what was accepted; energy trades need no schedule at the BRP."""
    accepted = [o for o in ctx.market_data.get("orderbook", []) if o.get("accepted_volume")]
    ctx.data["accepted_orders"] = accepted
    ctx.log("record_energy_result", "Recorded the accepted energy orders.",
            {"market_id": ctx.market_data.get("market_id"), "accepted": len(accepted),
             "volume_kw_total": round(sum(float(o["accepted_volume"]) for o in accepted), 2)})


ENERGY_CLEARING_STEPS = [record_energy_result]


def run_energy_bidding(agent, market_data: dict) -> MarketContext:
    """Run the energy bidding pipeline for one market-open event."""
    ctx = MarketContext(agent=agent, market_data=market_data)
    run_pipeline(ctx, ENERGY_BIDDING_STEPS, agent.pipeline_status, name="energy bidding")
    agent.last_energy_bid_trace = ctx.trace
    return ctx


def run_energy_clearing(agent, market_data: dict) -> MarketContext:
    """Run the energy clearing pipeline for one market-result event."""
    ctx = MarketContext(agent=agent, market_data=market_data)
    run_pipeline(ctx, ENERGY_CLEARING_STEPS, agent.pipeline_status, name="energy clearing")
    agent.clearing_traces.append(ctx.trace)
    return ctx
