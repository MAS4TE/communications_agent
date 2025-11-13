"""Core logic for CPU forecast preparation and parsing."""

from pathlib import Path
import re


def read_cpu_history(log_path: str = "data/cpu_history") -> list[dict]:
    """Read CPU usage history from a log file."""
    path = Path(log_path)
    if not path.exists():
        return []

    history = []
    pattern = re.compile(r"percent=([0-9.]+)")
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            match = pattern.search(line)
            if match:
                history.append({
                    "timestamp": line.split()[0],
                    "percent": float(match.group(1)),
                })
    return history


def prepare_forecast_payload(history: list[dict], prediction_length: int = 1) -> dict:
    """Prepare a forecast request payload for Chronos."""
    return {
        "history": [{"timestamp": h["timestamp"], "value": h["percent"]} for h in history],
        "prediction_length": prediction_length,
    }
