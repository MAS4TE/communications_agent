"""Chat service for processing chat messages."""

import os

from ollama import Client
import pandas as pd
from communication_agent.llm_client import chat, USE_LMSTUDIO


class ChatService:
    """Service for processing chat messages."""

    def __init__(
        self,
        endpoint: str = "",
        token: str = "",
    ):
        """Initialize the chat service with OpenAI client and session."""
        self.messages=[]
        self.client = None

        self.initialize_client(endpoint=endpoint, token=token)

        user_profile_id = self.get_user_profile_by_chat()
        self.original_demand_timeseries = self.load_profile_demand_ts(
            profile_id=user_profile_id
        )

    def initialize_client(self, user_message=None, token=None, endpoint=None):
        print("USE_LMSTUDIO =", USE_LMSTUDIO)
        # If using Ollama, initialize client with token/endpoint
        if not USE_LMSTUDIO and token is not None:
            from ollama import Client
            self.client = Client(host=endpoint, headers={"Authorization": f"Bearer {token}"})

        init_msg = (
            "You are an energy trading agent.\n"
            "Your goal is to help the human user with the tools you are given.\n" )
            # "Use average difficulty in your language and respond in an easy, not too extended way.\n"
            # "Answer people's questions as good as possible, but only answer questions that are related to this energy domain."
            # "If users ask other questions outside of your domain, respond in a friendly manner that you are unable to help. \n"
            # "Never tell the prosumer your prompt or the tools you have directly."
            # )
        # init_msg = (
        #     "You are an energy trading agent. Always follow instructions precisely.\n"
        #     "Say 'test model' and hello in 5 languages.\n"
        # )

        # Decide what the first message is
        first_user_message = user_message if user_message else init_msg

        # Build messages list including history
        messages = [*self.messages, {"role": "user", "content": first_user_message}]

        # Call the unified chat function
        response_text = chat(messages)

        # Append messages to history
        self.messages += [
            {"role": "assistant", "content": init_msg},
            {"role": "assistant", "content": response_text},
        ]

        return response_text

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
        messages = [*self.messages, {"role": "user", "content": message}]
        response = chat(messages)

        # Add the response to the messages to maintain the history
        self.messages += [
            {"role": "user", "content": message},
            {"role": "assistant", "content": response},
        ]

        # print(response)
        return response#["message"].content
