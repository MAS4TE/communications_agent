"""API routes package."""

from fastapi import APIRouter

from .routes.root_endpoint import router as root_router
from .routes.chat_endpoint import router as chat_router
from .routes.battery_endpoint import router as battery_router
from .routes.cpu_endpoint import router as cpu_router
from .routes.forecast_custom import router as forecast_custom
from .routes.preferences_endpoint import router as preferences_router
from .routes.profile_endpoint import router as profile_router

# Main API router
api_router = APIRouter()

# Include all route modules
api_router.include_router(root_router)
api_router.include_router(chat_router, prefix="/chat")
api_router.include_router(battery_router)
api_router.include_router(cpu_router)
api_router.include_router(forecast_custom)
api_router.include_router(preferences_router)
api_router.include_router(profile_router)