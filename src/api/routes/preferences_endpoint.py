"""Prosumer preferences endpoint."""
from fastapi import APIRouter
from pydantic import BaseModel
from api.services.prosumer.prosumer_service import ProsumerService

router = APIRouter(tags=["preferences"])

class PreferencesRequest(BaseModel):
    risk: str
    trading_preference: str

@router.get("/prosumer/preferences")
def get_prefs():
    service = ProsumerService()
    return service.get_preferences()

@router.post("/prosumer/preferences")
def save_prefs(prefs: PreferencesRequest):
    service = ProsumerService()
    service.save_preferences(prefs.risk, prefs.trading_preference)
    return {"status": "ok"}