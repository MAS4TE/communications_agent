# llm_utils/backends/lmstudio_agent.py
import lmstudio as lms
import json
from typing import Optional, List

from ..interfaces.agent import AgentLLM
from core.llm.tools.registry import tool_registry

from utils.ansi import BOLD_BLUE, BOLD_GREEN, RESET


# Tools that are only used by the pipeline and should never be exposed to the
# chatbot. LMStudio 1.5.0 now introspects raw function signatures, and these
# tools have pandas Series parameters that it can't parse into a JSON schema.
PIPELINE_ONLY_TOOLS = {
    "battery_utility_calculator",
    "forecast_timeseries_from_csv",
}


class LMStudioAgent(AgentLLM):
    """Agentic LM Studio LLM with tool use."""

    def __init__(self, model_name: str = "qwen2.5-7b-instruct-1m"):
        self.model_name = model_name
        self._model = lms.llm(model_name)

        self.messages: List[dict] = []
        self._chat = lms.Chat()
        self.response_chunks = []

        # Filter out pipeline-only tools — the chatbot should never call these
        # directly. They have complex parameter types (pandas Series) that
        # LMStudio 1.5.0 can't parse when introspecting function signatures.
        self.tools_to_use = [
            t for t in tool_registry.tools
            if t.__name__ not in PIPELINE_ONLY_TOOLS
        ]
        self.tool_schemas = [
            s for s in tool_registry.schemas
            if s.get("function", {}).get("name") not in PIPELINE_ONLY_TOOLS
        ]

        print(f"LMStudioAgent: loaded {len(self.tools_to_use)} chatbot tools:")
        for t in self.tools_to_use:
            print(f"  - {t.__name__}")

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
        # for msg in messages:
        #     if msg["role"] == "system":
        #         self._chat.add_user_message(f"System: {msg['content']}")
        #     elif msg["role"] == "user":
        #         self._chat.add_user_message(msg["content"])
        #     elif msg["role"] == "assistant":
        #         self._chat.add_assistant_response(msg["content"])

        # Keep only the last 10 messages (excluding system prompt)
        system_messages = [m for m in messages if m["role"] == "system"]
        non_system_messages = [m for m in messages if m["role"] != "system"]
        recent_messages = non_system_messages[-10:]  # last 10 only

        # Rebuild chat with system prompt + last 10 messages
        self._chat = lms.Chat()
        for msg in system_messages:
            self._chat.add_user_message(f"System: {msg['content']}")
        for msg in recent_messages[:-1]:  # all but the last
            if msg["role"] == "user":
                self._chat.add_user_message(msg["content"])
            elif msg["role"] == "assistant":
                self._chat.add_assistant_response(msg["content"])

        # Add the latest user message
        last = recent_messages[-1]
        if last["role"] == "user":
            self._chat.add_user_message(last["content"])
            

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