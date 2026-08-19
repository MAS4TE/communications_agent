"""Loading prosumer data from disk.

A "prosumer" is the household this agent represents. Their data lives in two
files under data/ (both git-ignored):

  - data/prosumers/prosumer_<id>.json     household appliances, home battery,
                                          battery capacity  -> shown in the UI
                                          and used in the chat system prompt
  - data/profile_data/profiles_usecases.csv   one row per profile with the
                                          battery size and location -> used by
                                          the bidding pipeline to decide whether
                                          this prosumer is a buyer or a seller

These are plain functions: pass the profile id, get a dict back. The agent's
*preferences* (which the user changes in the UI) are mutable session state and
live on the Agent object instead — see agent.py.
"""
import json

import pandas as pd

from config import DATA_DIR

PROFILES_CSV = DATA_DIR / "profile_data" / "profiles_usecases10.csv"
# PROFILES_CSV = DATA_DIR / "profile_data" / "profiles_usecases.csv"


# Sensible defaults until the user changes them in the UI panel.
DEFAULT_PREFERENCES = {
    "trading_preference": "Profit",     # "Profit" or "Green"
    "battery_tradeable_pct": 80,        # how much of the battery may be rented out
    "expertise": "Beginner",            # "Beginner" / "Intermediate" / "Expert"
    "trading_scope": "All",             # "Community" / "Country" / "All"
}


class MissingProsumerData(FileNotFoundError):
    """Raised when data/ (git-ignored) is not in place."""


def _require(path) -> None:
    if not path.exists():
        raise MissingProsumerData(
            f"{path} is missing. The data/ directory is git-ignored — copy the "
            f"prosumer profiles, price data and forecasts into {DATA_DIR} before "
            f"starting an agent (see the README)."
        )


def _profiles_table() -> pd.DataFrame:
    """The profiles_usecases table, indexed by profile_id.

    The CSV is written by hand and its first column is sometimes an unnamed
    export index and sometimes profile_id itself, so read it plainly and only
    then decide what the index is.
    """
    _require(PROFILES_CSV)
    df = pd.read_csv(PROFILES_CSV)
    df.columns = df.columns.str.strip()        # some columns have stray tabs
    df = df[[c for c in df.columns if not c.startswith("Unnamed")]]
    if "profile_id" not in df.columns:
        raise ValueError(f"{PROFILES_CSV} has no profile_id column (found: {list(df.columns)})")
    return df.set_index("profile_id")


def load_profile(profile_id: int) -> dict:
    """Household profile for the UI and chat prompt.

    Returns the prosumer_<id>.json contents (people, electric_car, heat_pump,
    solar_panels, home_battery, battery_capacity_kwh, ...) plus their location.
    """
    path = DATA_DIR / "prosumers" / f"prosumer_{profile_id}.json"
    _require(path)
    with open(path) as f:
        profile = json.load(f)

    table = _profiles_table()
    if profile_id in table.index:
        profile["location"] = table.loc[profile_id, "location"]
    return profile


def load_profile_metadata(profile_id: int) -> dict:
    """Trading-relevant profile row from profiles_usecases.csv.

    The important fields are ``battery_size_kwh`` (0 -> buyer, > 0 -> seller)
    and ``location``.
    """
    table = _profiles_table()
    if not table.index.is_unique:
        duplicates = sorted(table.index[table.index.duplicated()].unique().tolist())
        raise ValueError(f"profile_id is not unique in {PROFILES_CSV.name}: {duplicates}")
    if profile_id not in table.index:
        raise KeyError(
            f"profile_id {profile_id} is not in {PROFILES_CSV.name} "
            f"(known: {sorted(table.index.tolist())})"
        )
    return table.loc[profile_id].to_dict()
