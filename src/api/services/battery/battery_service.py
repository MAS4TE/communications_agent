# api/services/battery/battery_service.py
"""Battery service for battery status and operations."""

from fastapi import HTTPException

from core.domain.battery_logic import get_battery_metrics

class BatteryService:
    """API-facing service that wraps core battery logic."""

    def get_battery_status(self):
        try:
            return get_battery_metrics()
        except RuntimeError as e:
            raise HTTPException(status_code=404, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error accessing battery info: {str(e)}")

