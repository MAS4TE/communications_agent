"""Chat session handling for OpenAI interactions.

This module is used by the ChatService to manage OpenAI interactions
and maintain conversation state.
"""

import json

from openai import OpenAI

from fastapi_app.core.tools import Tools
from fastapi_app.models.tool_schemas import tool_schemas

class SolarChatSession:
    """Chat session for handling conversation with OpenAI models.
    
    This class is responsible for maintaining conversation state and 
    calling tools in response to user queries.
    """
    
    def __init__(self, client: OpenAI, prompt: str):
        self.client = client
        self.prompt = (
            "You are an expert assistant. Only answer questions related to batteries, solar energy, energy forecasts, "
            "and related technical topics. If asked about general knowledge or unrelated subjects, politely decline."
        )
        self.tools = Tools.get_tools() 
        self.tool_schemas = tool_schemas

        self.messages = [{"role": "system", "content": self.prompt}]

    def process_message(self, user_message: str):
        self.messages.append({"role": "user", "content": user_message})

        completion = self.client.chat.completions.create(
            model="gpt-4o-mini",
            messages=self.messages,
            functions=self.tool_schemas,
            function_call="auto",
        )

        message = completion.choices[0].message
        reply = message.content or ""

        # If the model wants to call a tool
        if message.function_call:
            tool_name = message.function_call.name
            tool_args = json.loads(message.function_call.arguments or "{}")

            tool_fn = next((t for t in self.tools if t.__name__ == tool_name), None)
            if tool_fn:
                tool_result = tool_fn(**tool_args)
                reply = f"{tool_name} result: {tool_result}"
            else:
                reply = f"Error: Tool '{tool_name}' is not available."

        self.messages.append({"role": "assistant", "content": reply})
        return reply