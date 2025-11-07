"""CPU service for CPU status and operations."""

import psutil
from fastapi import HTTPException

class CPUService:
    """Service for accessing CPU information and operations."""

    def get_cpu_status(self):
        """
        Get current CPU status using psutil.

        Returns:
            dict: CPU status information

        Raises:
            HTTPException: If CPU information cannot be accessed
        """
        try:
            percent = psutil.cpu_percent(interval=1)
            count = psutil.cpu_count()
            return {
                "percent": percent,
                "count": count
            }
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error accessing CPU info: {str(e)}")

    def log_cpu_usage(self, interval_minutes=5, log_path="data/cpu_history"):
        """
        Log CPU usage every `interval_minutes` minutes and append to log_path.
        """
        import time
        from pathlib import Path
        log_file = Path(log_path)
        log_file.parent.mkdir(parents=True, exist_ok=True)
        while True:
            status = self.get_cpu_status()
            timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
            log_entry = f"{timestamp} percent={status['percent']} count={status['count']}\n"
            with log_file.open("a", encoding="utf-8") as f:
                f.write(log_entry)
            time.sleep(interval_minutes * 60)