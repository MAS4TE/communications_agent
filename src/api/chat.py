"""Chat API endpoints."""
import sys

from fastapi import APIRouter, Depends

from models.chat import ChatRequest, ChatResponse
from services.chat.chat_service import ChatService
from core.tools import Tools
from models.tool_schemas import tool_schemas
from core.llm.factory import LLMFactory
from core.llm.tools.tools_manager import ToolManager


# Setup at module level
factory = LLMFactory()
llm = factory.create_from_yaml("D:/Repos2/mas4te/fastapi_app/src/configs/config_openai.yaml", agentic=True)

# Get all available tools and their schemas
tools = Tools.get_tools()
tool_manager = ToolManager(tools=tools, schemas=tool_schemas)
llm.tool_manager = tool_manager  # Attach tool manager to LLM instance


router = APIRouter(tags=["chat"])

chat_service = ChatService(llm=llm) # Singleton

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