# llm_utils/backends/lmstudio_agent.py
import lmstudio as lms
import json
from typing import Optional, List

from ..interfaces.agent import AgentLLM
from core.llm.tools.registry import tool_registry


from utils.ansi import BOLD_BLUE, BOLD_GREEN, RESET


class LMStudioAgent(AgentLLM):
    """Agentic LM Studio LLM with tool use."""

    def __init__(self, model_name: str = "qwen2.5-7b-instruct-1m"):
        self.model_name = model_name
        self._model = lms.llm(model_name)
        
        self.messages: List[dict] = []
        self._chat = lms.Chat()
        self.response_chunks = []

        self.tools_to_use = tool_registry.tools
        self.tool_schemas = tool_registry.schemas

    @property
    def llm(self):
        return self._model

    @property
    def chat(self):
        return self.messages

    @property
    def backend_name(self):
        return f"{self.model_name}-agent"

    def _print_bot_response(self, content):
        print(f"{BOLD_GREEN}{content}{RESET}", end="", flush=True)

    def _log_fragment(self, fragment, round_index=0):
        self.response_chunks.append(fragment.content)
        self._print_bot_response(fragment.content)

    def invoke(self, messages: list[dict], tools: list | None = None) -> str:
        """
        Agentic LMStudio invocation with tools.
        Streams fragments and collects final response.
        """
        tools_to_use = tools or self.tools_to_use

        # Reset chat and response chunks for new conversation
        self._chat = lms.Chat()
        self.response_chunks = []

        # Add messages to chat
        for msg in messages:
            if msg["role"] == "system":
                # Handle system messages as special user messages
                self._chat.add_user_message(f"System: {msg['content']}")
            elif msg["role"] == "user":
                self._chat.add_user_message(msg["content"])
            elif msg["role"] == "assistant":
                self._chat.add_assistant_response(msg["content"])

        # Call act with fragment callback
        self._model.act(
            self._chat,
            tools=tools_to_use,
            on_message=self.chat.append,
            on_prediction_fragment=self._log_fragment,
            config={
                "maxTokens": 1000,
                "temperature": 0.7,
                "toolSchemas": self.tool_schemas
            },
        )

        # Join fragments for final reply
        response = "".join(self.response_chunks)
        self.response_chunks = []  # Clear for next use
        return response
