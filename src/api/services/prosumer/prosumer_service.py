"""Prosumer service."""
import json
import os
from core.main_context import GLOBAL_PROFILE_ID
import pandas as pd

# In-memory preferences
_preferences = {
    "trading_preference": "Profit", 
    "battery_tradeable_pct": 80,
    "expertise": "Beginner",
    "trading_scope": "All",
}

class ProsumerService:
    def get_profile(self):
        path = os.path.join("data", "prosumers", f"prosumer_{GLOBAL_PROFILE_ID}.json")
        with open(path, "r") as f:
            profile = json.load(f)

        df = pd.read_csv("data/profile_data/profiles_usecases.csv", index_col=0)
        df = df.set_index("profile_id")
        if GLOBAL_PROFILE_ID in df.index:
            profile["location"] = df.loc[GLOBAL_PROFILE_ID, "location"]
        return profile
    
    def get_preferences(self):
        return _preferences

    def save_preferences(self, trading_preference: str, battery_tradeable_pct: int, expertise: str, trading_scope: str = "All"):
        _preferences["trading_preference"] = trading_preference
        _preferences["battery_tradeable_pct"] = battery_tradeable_pct
        _preferences["expertise"] = expertise
        _preferences["trading_scope"] = trading_scope