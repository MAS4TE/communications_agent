"""Central configuration for one communication agent.

Everything that used to be spread across configs/settings.py, the three
config_*.yaml files and assorted hard-coded constants now lives here, in one
place, as plain Python. No pydantic, no YAML indirection — just read the
constants you need.

Per-agent identity (which prosumer this process represents) comes from two
environment variables, set by start_agents.py / launch.py:

    PROFILE_ID   e.g. "84"     -> which prosumer profile to load
    AGENT_ID     e.g. "S_01"   -> this agent's name on the MQTT market
"""
import os
from pathlib import Path

import yaml


def _env_flag(name: str, default: bool) -> bool:
    """Read a boolean setting from the environment ("1", "true", "yes", "on")."""
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")

# --------------------------------------------------------------------------
# Paths
# --------------------------------------------------------------------------
SRC_DIR = Path(__file__).resolve().parent          # .../communication_agent/src
# Profiles, prices and forecasts. Git-ignored, so it can also live outside the
# checkout — point MAS4TE_DATA_DIR at it (used for tests and shared datasets).
DATA_DIR = Path(os.environ.get("MAS4TE_DATA_DIR", SRC_DIR / "data"))
CONTEXT_DIR = SRC_DIR / "context"                   # prompt context markdown
STATIC_DIR = SRC_DIR / "static"                     # web UI

# Secret files (git-ignored, expected to sit next to this file in src/)
MISTRAL_KEY_FILE = SRC_DIR / "mas4te_mistral_api_key.yml"
REST_API_KEY_FILE = SRC_DIR / "mas4te_restapi_key.yml"
MQTT_CREDENTIALS_FILE = SRC_DIR / "mas4tecontroller_mqtt_credentials.yml"

# --------------------------------------------------------------------------
# Agent identity (from environment)
# --------------------------------------------------------------------------
PROFILE_ID = int(os.environ.get("PROFILE_ID", 84))
AGENT_ID = os.environ.get("AGENT_ID", "S_01")

# --------------------------------------------------------------------------
# Locations
# --------------------------------------------------------------------------
SELLER_LOCATIONS = ["aachen", "juelich", "heerlen", "liege"]
LOCATION_COUNTRY = {
    "aachen": "germany",
    "juelich": "germany",
    "heerlen": "netherlands",
    "liege": "belgium",
}
DEFAULT_COUNTRY="germany"

# --------------------------------------------------------------------------
# Chronos forecasting service
# --------------------------------------------------------------------------
CHRONOS_URL = os.environ.get("CHRONOS_URL", "http://127.0.0.1:8000")
CHRONOS_TIMEOUT = 500

# --------------------------------------------------------------------------
# LLM backend
# --------------------------------------------------------------------------
# Which backend the chat assistant uses: "mistral", "openai", "lmstudio",
# "offline", or "auto". "auto" takes the first cloud backend whose API key is
# present and falls back to "offline" (no model, answers from raw data) so a
# missing key never stops the agent from trading.
LLM_BACKEND = os.environ.get("LLM_BACKEND", "auto")

# Settings per backend. Only the selected one is actually used.
LLM_CONFIGS = {
    "mistral": {
        "model_name": "mistral-small-latest",
        "base_url": "https://api.mistral.ai/v1",
        "api_key_env": "MISTRAL_API_KEY",
        "temperature": 0.0,
        "max_tokens": 1000,
    },
    "openai": {
        "model_name": "gpt-4o-mini",
        "base_url": None,                 # use OpenAI's default endpoint
        "api_key_env": "OPENAI_API_KEY",
        "temperature": 0.0,
        "max_tokens": 1000,
    },
    "lmstudio": {
        "model_name": "qwen2.5-7b-instruct-1m",
        "temperature": 0.7,
        "max_tokens": 1000,
    },
}

# --------------------------------------------------------------------------
# Optimiser
# --------------------------------------------------------------------------
# Which solver the Battery Utility Calculator uses. The BUC itself defaults to
# "gurobi", which we do not have a licence for, so every call must pass this.
SOLVER = os.environ.get("BUC_SOLVER", "appsi_highs")

# DRY_RUN computes everything but sends nothing outward: no orderbook to the
# market, no schedule to the battery or the BRP API. Used by smoke_test.py.
DRY_RUN = _env_flag("MAS4TE_DRY_RUN", False)

# --------------------------------------------------------------------------
# MQTT
# --------------------------------------------------------------------------
# ONLINE = talk to the real Jülich broker (TLS); offline = local broker.
MQTT_ONLINE = _env_flag("MQTT_ONLINE", False)

# Local broker — used for ASSUME (always) and for the battery when offline.
MQTT_LOCAL_BROKER = os.environ.get("MQTT_LOCAL_BROKER", "localhost")
MQTT_LOCAL_PORT = int(os.environ.get("MQTT_LOCAL_PORT", 1883))

# Live battery broker (only used when MQTT_ONLINE is True).
MQTT_BATTERY_BROKER = "ese-mqtt.ice.kfa-juelich.de"
MQTT_BATTERY_PORT = 8883
BATTERY_ID = "mas4te_1"

# --------------------------------------------------------------------------
# BRP REST API (where the battery schedule is sent for buyers)
# --------------------------------------------------------------------------
POWER_REQUEST_URL = "https://mas4te.nowum.fh-aachen.de/brp-api/power_request"


# --------------------------------------------------------------------------
# Secret loading
# --------------------------------------------------------------------------
def load_api_keys() -> None:
    """Read the git-ignored key files (if present) into environment variables.

    Call this once at startup, before building the LLM. Missing, empty or broken
    key files are not fatal: the chat assistant then runs on the offline backend
    (see llm/factory.py) and the market side keeps working either way. An API key
    already present in the environment always wins over the file.
    """
    if os.environ.get("MISTRAL_API_KEY") or not MISTRAL_KEY_FILE.exists():
        return
    try:
        with open(MISTRAL_KEY_FILE) as f:
            key = (yaml.safe_load(f) or {}).get("mistral_api_key", "")
    except (yaml.YAMLError, OSError, AttributeError) as error:
        print(f"CONFIG: ignoring unreadable {MISTRAL_KEY_FILE.name}: {error}")
        return
    if key:
        os.environ["MISTRAL_API_KEY"] = key


def rest_api_credentials() -> tuple[str, str]:
    """Return (username, password) for the BRP REST API from the key file."""
    if not REST_API_KEY_FILE.exists():
        raise FileNotFoundError(
            f"{REST_API_KEY_FILE} is missing. Buyers need it to send their battery "
            f"schedule to the BRP API. It is git-ignored; create it with:\n"
            f"  api:\n    username: ...\n    password: ..."
        )
    with open(REST_API_KEY_FILE) as f:
        config = yaml.safe_load(f)
    return config["api"]["username"], config["api"]["password"]


def mqtt_battery_credentials() -> tuple[str | None, str | None]:
    """Return (username, password) for the live battery broker, or (None, None)."""
    if not MQTT_ONLINE:
        return None, None
    with open(MQTT_CREDENTIALS_FILE) as f:
        credentials = yaml.safe_load(f)
    return credentials["username"], credentials["password"]
