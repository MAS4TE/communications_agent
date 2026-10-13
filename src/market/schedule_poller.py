"""Every minute: sum the incoming schedules with the agent's own and send the total to the battery."""
import logging
import time

import pandas as pd
import requests

from config import DRY_RUN, POWER_REQUEST_URL, rest_api_credentials
from requests.auth import HTTPBasicAuth

log = logging.getLogger("poller")

POLL_SECONDS = 60


def fetch_incoming(agent) -> list[pd.Series]:
    """Haalt alle schedules voor dit adres op als lijst van Series (W, index = tijd)."""
    username, password = rest_api_credentials()
    response = requests.get(
        POWER_REQUEST_URL,
        auth=HTTPBasicAuth(username, password),
        params={"blockchain_address": agent.blockchain_address},
        timeout=30,
    )
    response.raise_for_status()
    series = []
    for item in response.json():
        index = pd.to_datetime(item["time_steps"])
        series.append(pd.Series(item["power_rate_w"], index=index, dtype=float))
    log.info("GET %s -> %d schedules", response.url, len(series))
    return series

def sum_schedules(incoming: list[pd.Series], own_w: pd.Series | None) -> pd.Series:
    parts = incoming + ([own_w] if own_w is not None else [])
    total = pd.concat(parts, axis=1).fillna(0).sum(axis=1).sort_index()
    return total.resample("15min").sum()


def to_power_request(total_w: pd.Series, request_id: str) -> dict:
    return {
        "request_id": request_id,
        "time_steps": [t.strftime("%Y-%m-%dT%H:%M:%S") for t in total_w.index],
        "power_rate_w": [round(float(w)) for w in total_w],
    }

def shift_to_future(total_w: pd.Series) -> pd.Series:
    """Simulation runs in 2023; the battery only accepts time steps in the future."""
    start = pd.Timestamp.now(tz="UTC").tz_localize(None).ceil("15min") + pd.Timedelta(minutes=30)
    shifted = total_w.copy()
    shifted.index = shifted.index + (start - total_w.index.min())
    return shifted


def poll_loop(agent):
    last = None
    while True:
        try:
            incoming = fetch_incoming(agent)
            if incoming or agent.own_power_w is not None:
                total = sum_schedules(incoming, agent.own_power_w)
                if agent.market_window is None:
                    total = total.iloc[0:0]
                else:
                    start, end = (pd.Timestamp(t) for t in agent.market_window)
                    total = total[(total.index >= start) & (total.index < end)]
                if not total.empty and (last is None or not total.equals(last)):
                    if DRY_RUN:
                        log.info("dry run — would send %d steps to %s", len(total), agent.battery_id)
                    else:
                        shifted = shift_to_future(total)
                        log.info("battery send: %s -> %s (%d steps)",
                                 shifted.index.min(), shifted.index.max(), len(shifted))
                        log.info("battery send power_w: min=%.0f max=%.0f nonzero=%d",
                                shifted.min(), shifted.max(), int((shifted != 0).sum()))
                        agent.battery_client.send_power_request(
                            to_power_request(shifted, agent.blockchain_address))
                    last = total
        except Exception:
            log.exception("poll failed")
        time.sleep(POLL_SECONDS)