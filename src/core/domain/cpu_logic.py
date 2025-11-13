"""Core CPU logic, independent of FastAPI or API concerns."""

import psutil
from pathlib import Path
import time

def get_cpu_metrics() -> dict:
    """Return basic CPU metrics."""
    percent = psutil.cpu_percent(interval=1)
    count = psutil.cpu_count()
    return {"percent": percent, "count": count}


def log_cpu_usage(interval_minutes=5, log_path="data/cpu_history"):
    """Continuously log CPU usage to a file."""
    log_file = Path(log_path)
    log_file.parent.mkdir(parents=True, exist_ok=True)
    while True:
        metrics = get_cpu_metrics()
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        entry = f"{timestamp} percent={metrics['percent']} count={metrics['count']}\n"
        with log_file.open("a", encoding="utf-8") as f:
            f.write(entry)
        time.sleep(interval_minutes * 60)
