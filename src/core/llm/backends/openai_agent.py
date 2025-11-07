import json
from typing import List, Optional

from openai import OpenAI

from ..interfaces.agent import AgentLLM
from ..tools.tools_manager import ToolManager

class OpenAIAgent(AgentLLM):
    def __init__(
            self, 
            model_name="gpt-4o-mini", 
            tool_manager: Optional[ToolManager] = None, 
            api_key: Optional[str] = None
        ):
        self.model_name = model_name
        
        # Handle API key from either explicit parameter, environment, or authenticator
        if api_key is not None:
            self.api_key = api_key
        else:
            try:
                from dependencies.auth import OpenAIAuthenticator
                auth = OpenAIAuthenticator()
                self.api_key = auth.api_key
            except ImportError:
                # Fallback to environment variable if authenticator not available
                self.api_key = None  # OpenAI client will use OPENAI_API_KEY env var
        
        self.client = OpenAI(api_key=self.api_key)
        self.tool_manager = tool_manager or ToolManager()
        self.messages = []

    @property
    def llm(self):
        return self.client

    @property
    def chat(self):
        return self.messages

    @property
    def backend_name(self):
        return f"{self.model_name}-agent"

    def invoke(self, messages: list[dict], tools: list | None = None) -> str:
        # merge tools with tool manager if provided
        tools_to_use = tools or self.tool_manager.tools
        completion = self.client.chat.completions.create(
            model=self.model_name,
            messages=messages,
            functions=[{"name": t.__name__, "description": t.__doc__} for t in tools_to_use],
            function_call="auto",
        )

        msg = completion.choices[0].message
        reply = msg.content or ""

        if msg.function_call:
            name = msg.function_call.name
            args = msg.function_call.arguments or "{}"
            import json
            args_dict = json.loads(args)
            reply = f"{name} result: {self.tool_manager.call_tool(name, args_dict)}"

        return reply