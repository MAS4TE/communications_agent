"""API-facing CPU forecaster service."""

import requests

from fastapi import HTTPException

from core.domain.cpu_forecast_logic import read_cpu_history, prepare_forecast_payload
from configs.settings import Settings

settings = Settings()

class CPUForecaster:
    """Service that delegates forecasting to an external Chronos model."""

    def __init__(self, log_path="data/cpu_history", chronos_url=settings.CHRONOS_URL +"/forecast"):
        self.log_path = log_path
        self.chronos_url = chronos_url

    def forecast_cpu(self, prediction_length=1):
        """Read CPU history and request forecast from Chronos."""
        try:
            history = read_cpu_history(self.log_path)
            if not history:
                return {"median": None, "low": None, "high": None}

            payload = prepare_forecast_payload(history, prediction_length)
            resp = requests.post(self.chronos_url, json=payload)
            resp.raise_for_status()
            return resp.json()

        except requests.RequestException as e:
            raise HTTPException(status_code=502, detail=f"Chronos service error: {str(e)}")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Forecast processing error: {str(e)}")
