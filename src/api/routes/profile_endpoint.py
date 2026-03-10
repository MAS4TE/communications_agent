"""Prosumer profile endpoint."""
from fastapi import APIRouter
from api.services.prosumer.prosumer_service import ProsumerService

router = APIRouter(tags=["profile"])

@router.get("/prosumer/profile")
def get_profile():
    service = ProsumerService()
    return service.get_profile()