from pathlib import Path
import re
import requests

class CPUForecaster:
    def __init__(self, log_path="data/cpu_history", chronos_url="http://127.0.0.1:8000/forecast"):
        self.log_path = Path(log_path)
        self.chronos_url = chronos_url

    def forecast_cpu(self, prediction_length=1):
        """Read CPU history from log and get a forecast from Chronos."""
        if not self.log_path.exists():
            return {"median": None, "low": None, "high": None}

        history = []
        pattern = re.compile(r"percent=([0-9.]+)")
        with self.log_path.open("r", encoding="utf-8") as f:
            for line in f:
                match = pattern.search(line)
                if match:
                    history.append({
                        "timestamp": line.split()[0],  # or extract actual timestamp from line
                        "percent": float(match.group(1))
                    })

        if not history:
            return {"median": None, "low": None, "high": None}

        # Prepare payload for Chronos
        payload = {
            "history": [{"timestamp": h["timestamp"], "value": h["percent"]} for h in history],
            "prediction_length": prediction_length
        }

        # POST to Chronos
        resp = requests.post(self.chronos_url, json=payload)
        resp.raise_for_status()
        return resp.json()

        # Dummy fast response
        # median = sum(h["percent"] for h in history[-prediction_length:]) / max(prediction_length, 1)
        # return {
        #     "median": median,
        #     "low": median * 0.37,
        #     "high": median * 2.37
        # }