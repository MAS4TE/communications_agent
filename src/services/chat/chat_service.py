"""Chat service for processing chat messages."""

from .session import SolarChatSession

class ChatService:
    """Service for processing chat messages."""
    
    def __init__(self, llm):
        """Initialize the chat service with OpenAI client and session."""
        self.session = SolarChatSession(llm, prompt="You are a solar battery assistant.")

    def process_message(self, message: str) -> str:
        """
        Process a chat message and return the response.
        
        Args:
            message: The user's message
            
        Returns:
            str: The assistant's response
        """
        return self.session.process_message(message)