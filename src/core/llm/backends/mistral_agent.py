# core/llm/backends/mistral_agent.py
import json
from typing import List, Optional
from openai import OpenAI

from ..interfaces.agent import AgentLLM
from core.llm.tools.registry import tool_registry
from utils.ansi import BOLD_GREEN, RESET

PIPELINE_ONLY_TOOLS = {
    "battery_utility_calculator",
    "forecast_timeseries_from_csv",
}

class MistralAgent(AgentLLM):
    """Agentic Mistral LLM with tool use via OpenAI-compatible API."""

    def __init__(self, model_name: str = "mistral-small-latest"):
        import os
        self.model_name = model_name
        self._client = OpenAI(
            api_key=os.environ.get("MISTRAL_API_KEY"),
            base_url="https://api.mistral.ai/v1"
        )
        self.messages: List[dict] = []

        self.tools_to_use = [
            t for t in tool_registry.tools
            if t.__name__ not in PIPELINE_ONLY_TOOLS
        ]

        self.tool_schemas = []
        for s in tool_registry.schemas:
            # Get the name regardless of format
            name = s.get("name") or s.get("function", {}).get("name")
            if name in PIPELINE_ONLY_TOOLS:
                continue
            # Wrap only if not already wrapped
            if s.get("type") == "function":
                self.tool_schemas.append(s)
            else:
                self.tool_schemas.append({"type": "function", "function": s})

        print(f"MistralAgent: loaded {len(self.tools_to_use)} chatbot tools:")
        for t in self.tools_to_use:
            print(f"  - {t.__name__}")

    @property
    def llm(self):
        return self._client

    @property
    def chat(self):
        return self.messages

    @property
    def backend_name(self):
        return f"{self.model_name}-agent"

    def invoke(self, messages: list[dict], tools: list | None = None) -> str:
        """Agentic Mistral invocation with tool use loop."""

        # Keep last 10 non-system messages + system messages
        system_messages = [m for m in messages if m["role"] == "system"]
        non_system_messages = [m for m in messages if m["role"] != "system"]
        recent_messages = non_system_messages[-10:]
        current_messages = system_messages + recent_messages

        # Tool calling loop
        while True:
            response = self._client.chat.completions.create(
                model=self.model_name,
                messages=current_messages,
                tools=self.tool_schemas,
                tool_choice="auto",
                max_tokens=1000,
                temperature=0.0,
            )

            msg = response.choices[0].message

            # No tool call → return final answer
            if not msg.tool_calls:
                content = msg.content or ""
                print(f"{BOLD_GREEN}{content}{RESET}")
                return content

            # Append assistant message with tool calls
            current_messages.append({
                "role": "assistant",
                "content": msg.content,
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments
                        }
                    }
                    for tc in msg.tool_calls
                ]
            })

            # Execute each tool call and append results
            for tc in msg.tool_calls:
                tool_name = tc.function.name
                tool_args = json.loads(tc.function.arguments)

                # Find and call the matching tool function
                tool_fn = next(
                    (t for t in self.tools_to_use if t.__name__ == tool_name),
                    None
                )
                if tool_fn:
                    print(f"Calling tool: {tool_name}({tool_args})")
                    result = tool_fn(**tool_args)
                else:
                    result = f"Tool '{tool_name}' not found."

                current_messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": str(result)
                })