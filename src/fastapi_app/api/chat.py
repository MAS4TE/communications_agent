"""Chat API endpoints."""

from fastapi import APIRouter, Depends

from fastapi_app.models.chat import ChatRequest, ChatResponse
from fastapi_app.services.chat_service import ChatService

router = APIRouter(tags=["chat"])

chat_service = ChatService() # Singleton

# Dependency to get the chat service
def get_chat_service():
    return chat_service

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