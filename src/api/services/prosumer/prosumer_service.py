"""Prosumer service."""
import json
import os
from core.main_context import GLOBAL_PROFILE_ID

# In-memory preferences
_preferences = {
    "risk": "Medium",
    "trading_preference": "Profit"
}

class ProsumerService:
    def get_profile(self):
        path = os.path.join("data", "prosumers", f"prosumer_{GLOBAL_PROFILE_ID}.json")
        with open(path, "r") as f:
            return json.load(f)

    def get_preferences(self):
        return _preferences

    def save_preferences(self, risk: str, trading_preference: str):
        _preferences["risk"] = risk
        _preferences["trading_preference"] = trading_preference