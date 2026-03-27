"""Prosumer service."""
import json
import os
from core.main_context import GLOBAL_PROFILE_ID

# In-memory preferences
_preferences = {
    # "risk": "Medium",
    "trading_preference": "Profit", 
    "battery_tradeable_pct": 80,
    "expertise":"Beginner"
}

class ProsumerService:
    def get_profile(self):
        path = os.path.join("data", "prosumers", f"prosumer_{GLOBAL_PROFILE_ID}.json")
        with open(path, "r") as f:
            return json.load(f)

    def get_preferences(self):
        return _preferences

    def save_preferences(self, trading_preference: str, battery_tradeable_pct:int, expertise:str):#(self, risk: str, trading_preference: str, expertise: str):
        # _preferences["risk"] = risk
        _preferences["trading_preference"] = trading_preference
        _preferences["battery_tradeable_pct"] = battery_tradeable_pct
        _preferences["expertise"] = expertise