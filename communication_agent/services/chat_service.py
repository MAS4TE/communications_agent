"""Chat service for processing chat messages."""

from ollama import Client, chat
from openai import OpenAI
from communication_agent.core.session import SolarChatSession
from communication_agent.dependencies.auth import OpenAIAuthenticator


class ChatService:
    """Service for processing chat messages."""
    
    def __init__(self):
        """Initialize the chat service with OpenAI client and session."""

        token = ""
    
        self.client = Client(
            host='https://chat.idt.fh-aachen.de/ollama',
            headers={'Authorization': f'Bearer {token}'}
        )
        self.messages = []

    def process_message(self, message: str) -> str:
        """
        Process a chat message and return the response.
        
        Args:
            message: The user's message
            
        Returns:
            str: The assistant's response
        """
        response = self.client.chat(
            'gemma3:27b',
            messages=[*self.messages, {'role': 'user', 'content': message}],
        )

        # Add the response to the messages to maintain the history
        self.messages += [
            {'role': 'user', 'content': message},
            {'role': 'assistant', 'content': response.message.content},
        ]

        # print(response)
        return response["message"].content