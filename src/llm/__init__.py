"""Chat assistant: backends, prompt and tools.

Public API:
  - build_llm()             -> the configured ChatLLM backend
  - build_system_message()  -> the system prompt for one prosumer
  - build_chat_tools(agent) -> the tools the assistant may call
"""
from llm.base import ChatLLM, Tool
from llm.factory import build_llm
from llm.prompt import build_system_message
from llm.tools import build_chat_tools

__all__ = ["ChatLLM", "Tool", "build_llm", "build_system_message", "build_chat_tools"]
