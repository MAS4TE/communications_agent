from typing import Protocol, Any

class AgentLLM(Protocol):
    """Interface for all LLM backends that support chat and tool use."""

    @property
    def llm(self) -> Any:
        ...

    @property
    def chat(self) -> Any:
        ...

    @property
    def backend_name(self) -> str:
        ...

    def invoke(self, messages: list[dict], tools: list | None = None) -> str:
        ...
