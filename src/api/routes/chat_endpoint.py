"""Chat API endpoints."""
import sys

from fastapi import APIRouter, Depends, Request

from ..models.chat import ChatRequest, ChatResponse
from ..services.chat.chat_service import ChatService
from core.llm.prompts import BATTERY_ASSISTANT_PROMPT


router = APIRouter(tags=["chat"])

def get_chat_service(request: Request) -> ChatService:
    """Dependency that provides ChatService initialized with LLM from app state."""
    return ChatService(
        llm=request.app.state.llm, 
        prompt=BATTERY_ASSISTANT_PROMPT.system_message
    )


@router.post(
    "",
    response_model=ChatResponse,
    responses={
        200: {
            "description": "Successful response",
            "content": {
                "application/json": {
                    "example": {
                        "response": "Your battery is currently at 85% capacity and is charging."
                    }
                }
            }
        }
    },
    summary="Send a message to the chat assistant",
    description="Process a natural language message and get an AI-generated response related to solar battery information"
)
def process_chat(
    req: ChatRequest, 
    service: ChatService = Depends(get_chat_service)
):
    """
    Process a chat message and return the response.
    
    The message is processed by an AI assistant that can provide information
    about battery status and answer questions related to solar batteries.
    """
    reply = service.process_message(req.message)
    return {"response": reply}