from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List
import requests
from configs.settings import Settings

settings = Settings()
router = APIRouter()


class ForecastRequest(BaseModel):
    timestamps: List[str]
    values: List[float]
    prediction_length: int


@router.post("/forecast/custom")
def forecast_custom(req: ForecastRequest):
    if len(req.timestamps) != len(req.values):
        raise HTTPException(400, "timestamps and values length mismatch")

    # payload = {
    #     "history": [
    #         {"timestamp": ts, "value": v}
    #         for ts, v in zip(req.timestamps, req.values)
    #     ],
    #     "prediction_length": req.prediction_length,
    # }
    payload = {
        "timestamps": req.timestamps,
        "values": req.values,
        "prediction_length": req.prediction_length,
    }

    r = requests.post(
        f"{settings.CHRONOS_URL}/forecast/custom",
        json=payload,
        timeout=settings.CHRONOS_TIMEOUT,
        # timeout = 500,
    )
    r.raise_for_status()
    return r.json()
