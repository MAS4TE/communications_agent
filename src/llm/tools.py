"""The tools the chat assistant can call.

These are built fresh for a given agent (``build_chat_tools(agent)``) so each
tool closes over that agent's live data — its profile, its current preferences
and the trace of what the bidding/clearing pipeline last did. No global state,
no registry.

Note: the heavy pipeline functions (battery utility calculator, Chronos
forecasting) are deliberately NOT chat tools. They run inside the bidding
pipeline, not on demand from the chat.
"""
import json
from datetime import datetime

from llm.base import Tool

ONBOARDING_TEXT = """Welcome to MAS4TE! I'm here to help you participate in virtual energy storage trading.

What is virtual storage trading?
When you buy virtual storage bundles, you're renting space on someone else's physical battery. You can store your excess solar energy there when you produce more than you need, and retrieve it later when you need it - like a virtual energy bank account.

Anonymous community market:
You trade on a local community market where all transactions are anonymous. You can buy storage capacity from battery owners in your community without knowing who they are, and they don't know who you are either.

Optimize your energy costs:
Buy storage bundles when you need a place to store excess energy, and retrieve that energy later when you need it. This lets you use your own solar energy at night or on cloudy days without needing to buy an expensive physical battery yourself.

I can help you with:
- Finding available storage capacity to rent
- Understanding storage prices and your current storage usage
- Tracking how much energy you've stored and retrieved
- Optimizing when to store and when to retrieve energy

What would you like to explore first?"""


def _schema(name: str, description: str, properties: dict | None = None, required: list | None = None) -> dict:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {
                "type": "object",
                "properties": properties or {},
                "required": required or [],
            },
        },
    }


def build_chat_tools(agent) -> list[Tool]:
    """Return the list of tools bound to this agent's live data."""

    def get_current_time() -> dict:
        return {"current_time": datetime.now().isoformat()}

    def get_profile() -> dict:
        return agent.profile

    def get_preferences() -> dict:
        return agent.preferences

    def get_onboarding_info() -> str:
        return ONBOARDING_TEXT

    def explain_pipeline(pipeline: str = "bid", weeks_ago: int = 0) -> str:
        """weeks_ago: 0 = most recent, 1 = one week before that, up to 3 (max 4 stored)."""
        history = agent.bid_history if pipeline == "bid" else agent.clearing_traces

        if not history:
            return "The pipeline hasn't run yet, so there is nothing to explain."

        index = -1 - weeks_ago
        if abs(index) > len(history):
            return (
                f"Only {len(history)} trading round(s) are available to look back on "
                f"— that request goes further back than what's stored."
            )

        entry = history[index]
        trace = entry["trace"] if pipeline == "bid" else entry
        return json.dumps(trace, indent=2, default=str)

    return [
        Tool(get_current_time, _schema(
            "get_current_time",
            "Returns the current date and time in ISO format.",
        )),
        Tool(get_profile, _schema(
            "get_profile",
            "Returns the prosumer's household profile (people, appliances, home battery, location).",
        )),
        Tool(get_preferences, _schema(
            "get_preferences",
            "Returns the prosumer's current trading preferences (trading preference, "
            "battery tradeable percentage, expertise level, trading scope). Always call "
            "this when you need their current preferences — do not assume.",
        )),
        Tool(get_onboarding_info, _schema(
            "get_onboarding_info",
            "Returns a beginner-friendly introduction to MAS4TE virtual energy storage "
            "trading. Use when the user is new or asks how the platform works.",
        )),
        Tool(explain_pipeline, _schema(
            "explain_pipeline",
            "Returns what the energy trading pipeline did, so you can explain how a bid "
            "was made or what happened during market clearing. Call this whenever the user "
            "asks what the system did on their behalf, including questions about past "
            "trading rounds (e.g. 'last week', 'two weeks ago').",
            properties={
                "pipeline": {
                    "type": "string",
                    "enum": ["bid", "clearing"],
                    "description": "'bid' for the bidding pipeline, 'clearing' for market clearing.",
                },
                "weeks_ago": {
                    "type": "integer",
                    "description": "How many trading rounds back to look. 0 = most recent (default), "
                                    "1 = the round before that, up to 3. Only the last 4 rounds are stored.",
                },
            },
            required=["pipeline"],
        )),
    ]
