"""Battery service for battery status and operations."""

import psutil
from fastapi import HTTPException

class BatteryService:
    """Service for accessing battery information and operations."""
    
    def get_battery_status(self):
        """
        Get current battery status using psutil.
        
        Returns:
            dict: Battery status information
        
        Raises:
            HTTPException: If battery information cannot be accessed
        """
        try:
            battery = psutil.sensors_battery()
            if battery is None:
                raise HTTPException(status_code=404, detail="No battery found")
                
            # Determine status string
            status = "charging" if battery.power_plugged else "discharging"
            
            return {
                "percent": battery.percent,
                "power_plugged": battery.power_plugged,
                "secsleft": battery.secsleft if hasattr(battery, "secsleft") else None,
                "status": status
            }
        except Exception as e:
            # Re-raise the exception to be handled at the API level
            raise HTTPException(status_code=500, detail=f"Error accessing battery info: {str(e)}")