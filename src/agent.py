"""The Agent — one prosumer's autonomous trading agent.

One object holds everything one agent needs:

  - identity        : profile_id, agent_id
  - prosumer data   : profile, preferences (editable in the UI)
  - the chat brain  : the LLM, its tools, and the conversation history
  - the market link : the MQTT market and battery clients
  - pipeline memory : live status, the last bidding run, and the traces the chat
                      assistant reads back to explain what happened

How work flows through the agent, and why there is no asyncio anywhere:

    paho's MQTT thread  ->  self.jobs (a queue)  ->  the worker thread

The MQTT callback must return immediately — while it is running, paho cannot
send keepalive pings and the broker drops us. So the callback only puts the
message on a queue. One worker thread takes jobs off that queue and runs the
pipeline. Because there is exactly one worker, two pipeline runs can never
overlap and nothing needs locking.
"""
import logging
import queue
import threading

from llm import build_chat_tools, build_llm, build_system_message
from market.bidding import run_bidding
from market.clearing import run_clearing
from market.mqtt import BatteryClient, MarketClient
from market.pipeline import PipelineStatus
from prosumer import DEFAULT_PREFERENCES, load_profile

log = logging.getLogger("agent")


class Agent:
    def __init__(self, profile_id: int, agent_id: str):
        self.profile_id = profile_id
        self.agent_id = agent_id

        # Prosumer data.
        self.profile = load_profile(profile_id)
        self.preferences = dict(DEFAULT_PREFERENCES)

        # Chat brain.
        self.llm = build_llm()
        self.chat_tools = build_chat_tools(self)
        self.chat_history = [{
            "role": "system",
            "content": build_system_message(self.profile, self.preferences),
        }]

        # Pipeline memory.
        self.pipeline_status = PipelineStatus()
        self.bid_counter = 0
        self.last_bidding_data: dict = {}
        self.last_bid_trace: list = []
        self.clearing_traces: list = []

        # Market link and the one worker that runs pipelines.
        self.market_client = MarketClient(self)
        self.battery_client = BatteryClient(self)
        self.jobs: queue.Queue = queue.Queue()

    # -- lifecycle ---------------------------------------------------------
    def start(self):
        """Start the worker and connect both MQTT clients (call once)."""
        threading.Thread(target=self._work, name=f"{self.agent_id}-pipeline",
                         daemon=True).start()
        log.info("worker started profile=%s", self.profile_id)
        self.market_client.start()
        self.battery_client.start()

    def _work(self):
        """Run queued pipelines, one at a time, forever."""
        while True:
            pipeline, market_data = self.jobs.get()
            log.info("worker picked up %s (%d still queued)",
                     pipeline.__name__, self.jobs.qsize())
            try:
                pipeline(self, market_data)
            except Exception:
                # One bad market message must not kill the worker: log it and
                # stay ready for the next one.
                log.exception("%s failed — worker stays up for the next message",
                              pipeline.__name__)

    # -- market events (called from the MQTT thread) -----------------------
    def on_market_open(self, market_data: dict):
        self.jobs.put((run_bidding, market_data))
        log.debug("queued bidding (%d waiting)", self.jobs.qsize())

    def on_market_result(self, market_data: dict):
        self.jobs.put((run_clearing, market_data))
        log.debug("queued clearing (%d waiting)", self.jobs.qsize())

    # -- preferences -------------------------------------------------------
    def update_preferences(self, **changes):
        self.preferences.update(changes)

    # -- bidding -----------------------------------------------------------
    def next_bid_id(self) -> int:
        bid_id = self.bid_counter
        self.bid_counter += 1
        return bid_id

    # -- chat --------------------------------------------------------------
    def chat(self, message: str, preferences: dict | None = None) -> str:
        """Answer one chat message, keeping conversation history."""
        prefs = preferences or self.preferences

        if self.profile.get("home_battery"):
            role_context = (
                f"This prosumer is a seller (they own a "
                f"{self.profile.get('battery_capacity_kwh', 'unknown')} kWh battery and can rent out capacity). "
                f"They have set a maximum of {prefs.get('battery_tradeable_pct', 50)}% of their battery as tradeable. "
                f"The actual amount offered may be less, as the system picks the optimal bid."
            )
        else:
            role_context = (
                "This prosumer is a buyer (they rent battery capacity from others). They do not own a "
                "battery. Never mention battery_tradeable_pct or battery scheduling to them."
            )

        # A fresh system note so the assistant always uses the latest preferences.
        fresh_context = {
            "role": "system",
            "content": (
                f"trading_preference={prefs.get('trading_preference', 'Profit')}, "
                f"expertise={prefs.get('expertise', 'Beginner')}, "
                f"trading_scope={prefs.get('trading_scope', 'All')}, "
                f"risk_tolerance={prefs.get('risk_tolerance', 'Low')} (ignored when trading_preference is Green). "
                f"These are the latest values — ignore any earlier preference values in this conversation. {role_context}"
            ),
        }

        self.chat_history.append({"role": "user", "content": message})
        messages = self.chat_history[:-1] + [fresh_context, self.chat_history[-1]]
        reply = self.llm.invoke(messages, self.chat_tools)
        self.chat_history.append({"role": "assistant", "content": reply})
        return reply
