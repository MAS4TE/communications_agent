"""What every chat backend shares: a Tool and a ChatLLM interface.

A Tool bundles a plain Python function with the JSON schema the LLM needs to
call it. There is deliberately no registry and no decorator magic: the chat
assistant is given an explicit list of Tools (built in tools.py) and that's it.

A ChatLLM takes a list of chat messages plus the available tools and returns the
assistant's final text reply, running any tool calls along the way.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Callable


@dataclass
class Tool:
    """A callable the LLM may invoke, together with its JSON schema."""

    fn: Callable
    schema: dict                       # {"type": "function", "function": {"name": ...}}

    @property
    def name(self) -> str:
        return self.schema["function"]["name"]


class ChatLLM(ABC):
    """A chat model that can call tools."""

    @abstractmethod
    def invoke(self, messages: list[dict], tools: list[Tool]) -> str:
        """Run the conversation (with tool use) and return the final reply."""


def recent_messages(messages: list[dict], keep: int = 10) -> list[dict]:
    """Keep all system messages plus the last ``keep`` non-system messages.

    Conversations grow unbounded; this keeps the context small and cheap while
    always preserving the system prompt(s).
    """
    system = [m for m in messages if m["role"] == "system"]
    other = [m for m in messages if m["role"] != "system"]
    return system + other[-keep:]
