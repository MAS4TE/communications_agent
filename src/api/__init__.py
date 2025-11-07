"""API routes package."""

from fastapi import APIRouter

from .root import router as root_router
from .chat import router as chat_router
from .battery import router as battery_router
from .cpu import router as cpu_router

# Main API router
api_router = APIRouter()

# Include all route modules
api_router.include_router(root_router)
api_router.include_router(chat_router, prefix="/chat")
api_router.include_router(battery_router)
api_router.include_router(cpu_router)