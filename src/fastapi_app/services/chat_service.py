"""Chat service for processing chat messages."""

from openai import OpenAI
from fastapi_app.core.session import SolarChatSession
from fastapi_app.dependencies.auth import OpenAIAuthenticator

class ChatService:
    """Service for processing chat messages."""
    
    def __init__(self):
        """Initialize the chat service with OpenAI client and session."""
        auth = OpenAIAuthenticator()
        client = OpenAI(api_key=auth.api_key)
        self.session = SolarChatSession(client, prompt="You are a solar battery assistant.")
    
    def process_message(self, message: str) -> str:
        """
        Process a chat message and return the response.
        
        Args:
            message: The user's message
            
        Returns:
            str: The assistant's response
        """
        return self.session.process_message(message)