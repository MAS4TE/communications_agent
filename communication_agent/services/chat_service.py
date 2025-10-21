"""Chat service for processing chat messages."""

import os

from ollama import Client, chat
import pandas as pd


class ChatService:
    """Service for processing chat messages."""
    
    def __init__(
            self,
            endpoint: str,
            token: str,
        ):
        """Initialize the chat service with OpenAI client and session."""

        self.initialize_client(endpoint=endpoint, token=token)
        
        
        user_profile_id = self.get_user_profile_by_chat()
        self.original_demand_timeseries = self.load_profile_demand_ts(profile_id=user_profile_id)

    def initialize_client(self, endpoint: str = None, token: str = None):

        self.client = Client(
            host=endpoint,
            headers={'Authorization': f'Bearer {token}'}
        )
        self.messages = []

        init_msg = (
            "You are an energy trading agent.\n"
            "You're goal is to help the user optimize their use of a storage system if they have one installed.\n" \
            "If the user does not have a storage system, you should help them understand the benefits of renting one from the storage market.\n"
            "For this, we first need to find out if the user has a storage system installed and what their energy consumption patterns are.\n"
        )

        response = self.client.chat(
            'gemma3:27b',
            messages=[*self.messages, {'role': 'user', 'content': init_msg}],
        )

        self.messages += [
            {'role': 'assistant', 'content': init_msg},
            {'role': 'assistant', 'content': response.message.content},
        ]


    def get_user_profile_by_chat(self):
        """Retrieve user profile information."""
        # TODO OU implement

        self.user_profile_id = 0


    def load_profile_demand_ts(self, profile_id: int) -> list[int]:

        # TODO OU implement
        filepath = os.path.join(os.path.dirname(__file__), "profile_0.csv")

        return pd.read_csv(filepath)["load_w"].values


    def process_message(
            self,
            message: str,
            model: str = "gemma3:27b",
        ) -> str:
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