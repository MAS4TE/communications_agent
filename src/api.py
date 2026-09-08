"""All HTTP endpoints in one place.

The web UI (static/index.html) talks to exactly these routes:

  GET  /                       the chat UI
  POST /chat                   send a message, get the assistant's reply
  GET  /prosumer/profile       the household profile (shown in the side panel)
  GET  /prosumer/preferences   the current trading preferences
  POST /prosumer/preferences   save new preferences
  GET  /pipeline/status        live progress of the bidding/clearing pipeline

Every route reads the one Agent from app.state — there is no global state.
"""
from fastapi import APIRouter, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel

from agent import Agent
from config import STATIC_DIR
from prosumer import load_previous_week_energy_kwh

router = APIRouter()


def get_agent(request: Request) -> Agent:
    return request.app.state.agent


class ChatRequest(BaseModel):
    message: str
    preferences: dict | None = None


class PreferencesRequest(BaseModel):
    trading_preference: str
    battery_tradeable_pct: int
    expertise: str
    trading_scope: str
    risk_tolerance: str


@router.get("/")
def index():
    return FileResponse(STATIC_DIR / "index.html")


@router.post("/chat")
def chat(body: ChatRequest, request: Request):
    reply = get_agent(request).chat(body.message, body.preferences)
    return {"response": reply}


@router.get("/prosumer/profile")
def prosumer_profile(request: Request):
    return get_agent(request).profile


@router.get("/prosumer/preferences")
def get_preferences(request: Request):
    return get_agent(request).preferences

@router.get("/prosumer/last-trade-summary")
def last_trade_summary(request: Request):
    return get_agent(request).last_trade_summary


@router.post("/prosumer/preferences")
def save_preferences(body: PreferencesRequest, request: Request):
    get_agent(request).update_preferences(
        trading_preference=body.trading_preference,
        battery_tradeable_pct=body.battery_tradeable_pct,
        expertise=body.expertise,
        trading_scope=body.trading_scope,
        risk_tolerance=body.risk_tolerance,
    )
    return {"status": "ok"}


@router.get("/pipeline/status")
def pipeline_status(request: Request):
    return get_agent(request).pipeline_status.snapshot()

@router.get("/prosumer/energy-week")
def energy_week(request: Request):
    agent = get_agent(request)
    if not agent.last_window:
        return {"days": [], "demand_kwh": [], "solar_kwh": []}
    return load_previous_week_energy_kwh(agent.profile_id, window_start=agent.last_window["start"])