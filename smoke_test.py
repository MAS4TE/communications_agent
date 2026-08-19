"""Run both pipelines once, without a broker, ASSUME or Chronos.

This is the quickest way to answer "is my install working?" and "did my change
break the bidding logic?". It builds a real Agent, feeds it a made-up
market_open for a window you choose, then feeds it a made-up clearing result
that accepts the first order, and prints what every step did.

    python smoke_test.py --profile 84
    python smoke_test.py --profile 3 --start 2026-01-01T08:00 --hours 1

It runs with MAS4TE_DRY_RUN=1, so nothing leaves the process: no orderbook is
published, no schedule is POSTed to the BRP API and none is sent to the battery.
One optimiser solve happens per candidate volume (per location, for buyers), so
keep --hours small on a slow machine.
"""
import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--profile", type=int, required=True, help="PROFILE_ID to load")
    parser.add_argument("--agent", default="TEST_01", help="AGENT_ID to use")
    parser.add_argument("--start", default="2026-01-01T08:00", help="window start (ISO)")
    parser.add_argument("--hours", type=float, default=1.0, help="window length in hours")
    args = parser.parse_args()

    os.environ.setdefault("PROFILE_ID", str(args.profile))
    os.environ.setdefault("AGENT_ID", args.agent)
    # Everything is computed, nothing is sent: no orderbook to the market and no
    # schedule to the battery or the BRP API. Set before config is imported.
    os.environ["MAS4TE_DRY_RUN"] = "1"

    import pandas as pd

    import config
    import logging_setup
    from agent import Agent
    from market.bidding import run_bidding
    from market.clearing import run_clearing

    logging_setup.setup(args.agent)
    config.load_api_keys()
    print(f"data dir : {config.DATA_DIR}")
    print(f"solver   : {config.SOLVER}")

    # Built but deliberately not started: no worker thread, no MQTT connection.
    agent = Agent(profile_id=args.profile, agent_id=args.agent)
    print(f"agent    : {agent.agent_id}, profile {agent.profile_id}\n")

    start = pd.to_datetime(args.start)
    end = start + pd.Timedelta(hours=args.hours)
    market_open = {"status": "market_open", "products": [
        {"start_time": start.isoformat(), "end_time": end.isoformat()}
    ]}

    print("=== bidding ===")
    bid = run_bidding(agent, market_open)
    _print_trace(bid.trace)

    orderbook = bid.data.get("orderbook", [])
    print(f"\norderbook: {len(orderbook)} orders")
    for order in orderbook[:5]:
        print(f"  {order['bid_id']:24} {order['volume']:>6} kWh @ {order['price']:.4f} EUR/kWh")
    if len(orderbook) > 5:
        print(f"  ... and {len(orderbook) - 5} more")

    if not orderbook:
        print("\nFAIL: bidding produced no orders")
        return 1

    print("\n=== clearing (pretending the first order was accepted) ===")
    accepted = dict(orderbook[0], accepted_volume=orderbook[0]["volume"], accepted_price=0.05)
    clearing = run_clearing(agent, {"msg": "market result", "orderbook": [accepted]})
    _print_trace(clearing.trace)

    print("\nOK — both pipelines completed")
    return 0


def _print_trace(trace: list) -> None:
    for entry in trace:
        print(f"  {entry['step']:28} {entry['description']}")
        if entry["metadata"]:
            print(f"  {'':28} {json.dumps(entry['metadata'], default=str)}")


if __name__ == "__main__":
    sys.exit(main())
