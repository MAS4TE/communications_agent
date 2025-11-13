# core/llm/tools/cpu_forecast_tool.py
from core.llm.tools.decorators import tool, trace_tool
from core.domain.cpu_forecast_logic import read_cpu_history, prepare_forecast_payload
from configs.settings import Settings
import requests

settings = Settings()

@tool(
    schema={
        "type": "function",
        "function": {
            "name": "get_cpu_forecast",
            "description": "Returns the average CPU usage percent from the log as a forecast.",
            "parameters": {
                "type": "object",
                "properties": {
                    "prediction_length": {
                        "type": "number",
                        "description": "Number of time steps to forecast",
                        "default": 1
                    }
                },
                "required": [],
            }
        }
    }
)
@trace_tool
def get_cpu_forecast(prediction_length: int = 1):
    """Get CPU usage forecast from Chronos service."""
    log_path = settings.CPU_LOG_PATH
    chronos_url = f"{settings.CHRONOS_URL}/forecast"

    history = read_cpu_history(log_path)
    if not history:
        return {"error": "No CPU history found at specified log path."}

    payload = prepare_forecast_payload(history, prediction_length)

    try:
        response = requests.post(chronos_url, json=payload, timeout=settings.CHRONOS_TIMEOUT)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        return {"error": f"Chronos request failed: {e}"}
