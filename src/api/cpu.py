"""CPU API endpoints."""
from pathlib import Path
import re

from fastapi import APIRouter, Depends, HTTPException

from fastapi_app.models.cpu import CPUStatus
from fastapi_app.services.cpu.cpu_service import CPUService
from fastapi_app.services.cpu.cpu_forecaster import CPUForecaster

router = APIRouter(prefix="/cpu", tags=["cpu"])

def get_cpu_service():
    return CPUService()

@router.get(
    "/status",
    response_model=CPUStatus,
    responses={
        200: {
            "description": "Successful response",
            "content": {
                "application/json": {
                    "example": {
                        "percent": 23.5,
                        "count": 8
                    }
                }
            }
        },
        500: {"description": "Error accessing CPU information"}
    },
    summary="Get current CPU status",
    description="Retrieves the current CPU usage percentage and CPU core count"
)
def get_cpu_status(
    service: CPUService = Depends(get_cpu_service)
):
    """
    Get the current CPU status.

    Returns the current CPU usage percentage and CPU core count.
    """
    return service.get_cpu_status()

@router.get("/forecast")
def get_cpu_forecast():
    forecaster = CPUForecaster()
    return forecaster.average_percent()

@router.get("/history")
def get_cpu_history():
    log_file = Path("data/cpu_history")
    history = []
    pattern = re.compile(r"^(.*?) percent=([0-9.]+) count=(\d+)")
    if log_file.exists():
        with log_file.open("r", encoding="utf-8") as f:
            for line in f:
                match = pattern.match(line.strip())
                if match:
                    timestamp, percent, count = match.groups()
                    history.append({
                        "timestamp": timestamp,
                        "percent": float(percent),
                        "count": int(count)
                    })
    return history