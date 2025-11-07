# llm_utils/backends/lmstudio_agent.py
import lmstudio as lms
import json
from typing import Optional, List

from ..interfaces.agent import AgentLLM
from ..tools.tools_manager import ToolManager

from utils.ansi import BOLD_BLUE, BOLD_GREEN, RESET


class LMStudioAgent(AgentLLM):
    """Agentic LM Studio LLM with tool use."""

    def __init__(self, model_name: str = "qwen2.5-7b-instruct-1m", tool_manager: Optional[ToolManager] = None):
        self.model_name = model_name
        self._model = lms.llm(model_name)
        self.tool_manager = tool_manager or ToolManager()
        self.messages: List[dict] = []
        self._chat = lms.Chat()
        self.response_chunks = []

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
        tools_to_use = tools or self.tool_manager.tools
        schemas_to_use = self.tool_manager.schemas if self.tool_manager else []

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

        # Prepare tools with default arguments
        def wrap_tool(tool_fn):
            def wrapped(**args):
                if tool_fn.__name__ == 'get_cpu_forecast' and 'prediction_length' not in args:
                    args['prediction_length'] = 1
                return tool_fn(**args)
            wrapped.__name__ = tool_fn.__name__
            wrapped.__doc__ = tool_fn.__doc__
            return wrapped

        # Wrap each tool with default argument handling
        tools_with_defaults = [wrap_tool(tool) for tool in tools_to_use]

        # Call act with fragment callback
        self._model.act(
            self._chat,
            tools=tools_with_defaults,
            on_message=self.chat.append,
            on_prediction_fragment=self._log_fragment,
            config={
                "maxTokens": 1000,
                "temperature": 0.7,
                "toolSchemas": schemas_to_use
            },
        )

        # Join fragments for final reply
        response = "".join(self.response_chunks)
        self.response_chunks = []  # Clear for next use
        return response
