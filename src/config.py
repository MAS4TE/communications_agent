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

# --------------------------------------------------------------------------
# Paths
# --------------------------------------------------------------------------
SRC_DIR = Path(__file__).resolve().parent          # .../communication_agent/src
DATA_DIR = SRC_DIR / "data"                         # profiles, prices, forecasts, ...
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
# Chronos forecasting service
# --------------------------------------------------------------------------
CHRONOS_URL = "http://127.0.0.1:8000"
CHRONOS_TIMEOUT = 500

# --------------------------------------------------------------------------
# LLM backend
# --------------------------------------------------------------------------
# Which backend the chat assistant uses: "mistral", "openai" or "lmstudio".
LLM_BACKEND = "mistral"

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
# MQTT
# --------------------------------------------------------------------------
# ONLINE = talk to the real Jülich broker (TLS); offline = local broker.
MQTT_ONLINE = False

# Local broker — used for ASSUME (always) and for the battery when offline.
MQTT_LOCAL_BROKER = "localhost"
MQTT_LOCAL_PORT = 1883

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

    Call this once at startup, before building the LLM. Missing files are fine
    in development — the corresponding feature just won't work.
    """
    if MISTRAL_KEY_FILE.exists():
        with open(MISTRAL_KEY_FILE) as f:
            os.environ["MISTRAL_API_KEY"] = yaml.safe_load(f).get("mistral_api_key", "")


def rest_api_credentials() -> tuple[str, str]:
    """Return (username, password) for the BRP REST API from the key file."""
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
