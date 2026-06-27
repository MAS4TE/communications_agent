"""The communication agent as a FastAPI app.

One process = one agent = one prosumer. Which prosumer is decided by the
PROFILE_ID and AGENT_ID environment variables (see config.py). Run several at
once with start_agents.py.

Run a single agent directly with:

    cd src
    PROFILE_ID=84 AGENT_ID=S_01 uvicorn main:app --port 8002

On startup the app builds the Agent (which loads the profile, builds the LLM and
connects to MQTT) and stores it on app.state for the HTTP routes to use.
"""
from contextlib import asynccontextmanager

import asyncio

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

import config
from agent import Agent
from api import router


@asynccontextmanager
async def lifespan(app: FastAPI):
    config.load_api_keys()
    agent = Agent(
        profile_id=config.PROFILE_ID,
        agent_id=config.AGENT_ID,
        loop=asyncio.get_running_loop(),
    )
    agent.connect()
    app.state.agent = agent
    print(f"AGENT {agent.agent_id} (profile {agent.profile_id}) ready")
    yield


app = FastAPI(title="MAS4TE Communication Agent", version="0.1.0", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=config.STATIC_DIR), name="static")
app.include_router(router)
