"""The communication agent as a FastAPI app.

One process = one agent = one prosumer. Which prosumer is decided by the
PROFILE_ID and AGENT_ID environment variables (see config.py). Start several at
once with launch.py.

Run a single agent directly with:

    cd src
    PROFILE_ID=84 AGENT_ID=S_01 python -m uvicorn main:app --port 8002

Importing this module builds the agent (loads the profile, builds the LLM) and
starts it (its worker thread and both MQTT clients). The HTTP routes in api.py
read that one agent off app.state. Nothing here is async: FastAPI runs the plain
`def` routes on its own threadpool, and the market side lives on the agent's
worker thread.
"""
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

import config
from agent import Agent
from api import router
from market.buc_debug import enable_if_requested

config.load_api_keys()
enable_if_requested()               # BUC_DEBUG=1 traces every optimiser solve

agent = Agent(profile_id=config.PROFILE_ID, agent_id=config.AGENT_ID)
agent.start()
print(f"AGENT {agent.agent_id} (profile {agent.profile_id}) ready")

app = FastAPI(title="MAS4TE Communication Agent", version="0.1.0")
app.state.agent = agent
app.mount("/static", StaticFiles(directory=config.STATIC_DIR), name="static")
app.include_router(router)
