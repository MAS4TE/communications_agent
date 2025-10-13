"""API routes package."""

from fastapi import APIRouter

from fastapi_app.api.root import router as root_router
from fastapi_app.api.chat import router as chat_router
from fastapi_app.api.battery import router as battery_router

# Main API router
api_router = APIRouter()

# Include all route modules
api_router.include_router(root_router)
api_router.include_router(chat_router, prefix="/chat")
api_router.include_router(battery_router)