"""Battery API endpoints."""

from fastapi import APIRouter, Depends, HTTPException

from fastapi_app.models.battery import BatteryStatus
from fastapi_app.services.battery.battery_service import BatteryService

router = APIRouter(prefix="/battery", tags=["battery"])

# Dependency to get the battery service
def get_battery_service():
    return BatteryService()

@router.get(
    "/status", 
    response_model=BatteryStatus,
    responses={
        200: {
            "description": "Successful response",
            "content": {
                "application/json": {
                    "example": {
                        "percent": 85.4,
                        "power_plugged": True,
                        "secsleft": 3600,
                        "status": "charging"
                    }
                }
            }
        },
        404: {"description": "No battery found on this system"},
        500: {"description": "Error accessing battery information"}
    },
    summary="Get current battery status",
    description="Retrieves the current battery status including charge percentage, power state, and time remaining"
)
def get_battery_status(
    service: BatteryService = Depends(get_battery_service)
):
    """
    Get the current battery status.
    
    Returns the current charge percentage, whether power is plugged in,
    estimated time remaining, and charging status.
    """
    return service.get_battery_status()