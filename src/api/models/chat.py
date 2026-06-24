from pydantic import BaseModel
from typing import Optional, Dict, Any

class ChatRequest(BaseModel):
    message: str
    preferences: Optional[Dict[str, Any]] = None

class ChatResponse(BaseModel):
    response: str