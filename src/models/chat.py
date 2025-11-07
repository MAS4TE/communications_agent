"""Chat-related data models and schemas."""

from pydantic import BaseModel

class ChatRequest(BaseModel):
    """Chat request model containing user message."""
    message: str

class ChatResponse(BaseModel):
    """Chat response model containing assistant's reply."""
    response: str