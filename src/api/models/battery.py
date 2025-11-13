"""Battery-related data models and schemas."""

from pydantic import BaseModel

class BatteryStatus(BaseModel):
    """Battery status information model."""
    percent: float
    power_plugged: bool
    secsleft: int = None  # Optional
    status: str = None    # Optional

