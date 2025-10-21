"""API routes package."""

from fastapi import APIRouter

from communication_agent.api.root import router as root_router
from communication_agent.api.chat import router as chat_router
from communication_agent.api.battery import router as battery_router

# Main API router
api_router = APIRouter()

# Include all route modules
api_router.include_router(root_router)
api_router.include_router(chat_router, prefix="/chat")
api_router.include_router(battery_router)