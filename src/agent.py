"""The Agent — one prosumer's autonomous trading agent.

This single object replaces the old grab-bag of module globals and get/set
functions (main_context.py): it holds everything one agent needs and is passed
around explicitly.

It owns:
  - identity        : profile_id, agent_id
  - prosumer data   : profile, preferences (editable in the UI)
  - the chat brain  : the LLM, its tools, and the conversation history
  - the market link : the MQTT market and battery clients
  - pipeline memory : live status, the last bidding run, and trace history that
                      the chat assistant reads back to explain what happened

The two ``handle_*`` methods are the entry points the MarketClient calls when an
MQTT message arrives; the lock ensures only one pipeline runs at a time.
"""
import asyncio

from llm import build_chat_tools, build_llm, build_system_message
from market.bidding import run_bidding
from market.clearing import run_clearing
from market.flow import PipelineStatus
from market.mqtt import BatteryClient, MarketClient
from prosumer import DEFAULT_PREFERENCES, load_profile


class Agent:
    def __init__(self, profile_id: int, agent_id: str, loop: asyncio.AbstractEventLoop):
        self.profile_id = profile_id
        self.agent_id = agent_id
        self.loop = loop

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
        self.lock = asyncio.Lock()
        self.bid_counter = 0
        self.last_bidding_data: dict = {}
        self.last_bid_trace: list = []
        self.clearing_traces: list = []

        # Market link.
        self.market_client = MarketClient(self)
        self.battery_client = BatteryClient(self)

    # -- lifecycle ---------------------------------------------------------
    def connect(self):
        """Connect both MQTT clients (call once at startup)."""
        self.market_client.start()
        self.battery_client.start()

    # -- preferences -------------------------------------------------------
    def update_preferences(self, **changes):
        self.preferences.update(changes)

    # -- bidding -----------------------------------------------------------
    def next_bid_id(self) -> int:
        bid_id = self.bid_counter
        self.bid_counter += 1
        return bid_id

    # -- market events (called from the MQTT thread via the event loop) ----
    async def handle_market_open(self, market_data: dict):
        async with self.lock:
            await run_bidding(self, market_data)

    async def handle_market_clearing(self, market_data: dict):
        async with self.lock:
            await run_clearing(self, market_data)

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
                f"IMPORTANT: The prosumer's current preferences RIGHT NOW are: "
                f"trading_preference={prefs.get('trading_preference', 'Profit')}, "
                f"expertise={prefs.get('expertise', 'Beginner')}. These are the latest values — "
                f"ignore any earlier preference values in this conversation. {role_context}"
            ),
        }

        self.chat_history.append({"role": "user", "content": message})
        messages = self.chat_history[:-1] + [fresh_context, self.chat_history[-1]]
        reply = self.llm.invoke(messages, self.chat_tools)
        self.chat_history.append({"role": "assistant", "content": reply})
        return reply
