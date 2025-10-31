"""CPU-related data models and schemas."""

from pydantic import BaseModel

class CPUStatus(BaseModel):
    """CPU status information model."""
    percent: float
    count: int