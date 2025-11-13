import json
from typing import List, Optional

from openai import OpenAI

from ..interfaces.agent import AgentLLM
from core.llm.tools.registry import tool_registry

class OpenAIAgent(AgentLLM):
    def __init__(
            self, 
            model_name="gpt-4o-mini", 
            api_key: Optional[str] = None
        ):
        self.model_name = model_name
        
        # Handle API key from either explicit parameter, environment, or authenticator
        if api_key is not None:
            self.api_key = api_key
        else:
            try:
                from utils.auth import OpenAIAuthenticator
                auth = OpenAIAuthenticator()
                self.api_key = auth.api_key
            except ImportError:
                # Fallback to environment variable if authenticator not available
                self.api_key = None  # OpenAI client will use OPENAI_API_KEY env var
        
        self.client = OpenAI(api_key=self.api_key)
        self.messages = []

        self.tools = tool_registry.tools
        self.schemas = tool_registry.schemas

    @property
    def llm(self):
        return self.client

    @property
    def chat(self):
        return self.messages

    @property
    def backend_name(self):
        return f"{self.model_name}-agent"

    def invoke(self, messages: list[dict]) -> str:
        # merge tools with tool manager if provided
        functions = [
            s["function"] if "function" in s else s
            for s in tool_registry.schemas
        ]
        
        completion = self.client.chat.completions.create(
            model=self.model_name,
            messages=messages,
            functions=functions,
            function_call="auto",
        )

        msg = completion.choices[0].message
        reply = msg.content or ""

        if hasattr(msg, "function_call") and msg.function_call:
            name = msg.function_call.name
            args = msg.function_call.arguments or "{}"
            args_dict = json.loads(args)

            # Find the matching tool by name
            for fn, schema in zip(tool_registry.tools, tool_registry.schemas):
                fn_name = schema.get("function", {}).get("name", schema.get("name"))
                if fn_name == name:
                    result = fn(**args_dict)
                    reply = f"{name} result: {result}"
                    break

        return reply