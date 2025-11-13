"""CPU service for API-facing operations."""

from fastapi import HTTPException
from core.domain.cpu_logic import get_cpu_metrics, log_cpu_usage


class CPUService:
    """API-facing service that wraps core CPU logic."""

    def get_cpu_status(self):
        try:
            return get_cpu_metrics()
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error accessing CPU info: {str(e)}")

    def log_cpu_usage(self, interval_minutes=5, log_path="data/cpu_history"):
        """Delegate logging to domain logic."""
        try:
            log_cpu_usage(interval_minutes=interval_minutes, log_path=log_path)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error logging CPU usage: {str(e)}")
