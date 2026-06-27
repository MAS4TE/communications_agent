"""Chat backend for a local LM Studio model.

LM Studio runs the model locally and has its own Python SDK (it does not speak
the OpenAI protocol), so it gets its own backend. It streams the reply in
fragments, which we collect and join into the final text.
"""
import lmstudio as lms

from llm.base import ChatLLM, Tool


class LMStudioLLM(ChatLLM):
    def __init__(self, model_name: str, temperature: float = 0.7, max_tokens: int = 1000):
        self.model_name = model_name
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.model = lms.llm(model_name)

    def invoke(self, messages: list[dict], tools: list[Tool]) -> str:
        # LM Studio has no "system" role, so we fold system prompts in as user
        # messages and keep only the last 10 turns of the actual conversation.
        system = [m for m in messages if m["role"] == "system"]
        other = [m for m in messages if m["role"] != "system"][-10:]

        chat = lms.Chat()
        for message in system:
            chat.add_user_message(f"System: {message['content']}")
        for message in other[:-1]:
            if message["role"] == "user":
                chat.add_user_message(message["content"])
            elif message["role"] == "assistant":
                chat.add_assistant_response(message["content"])
        if other and other[-1]["role"] == "user":
            chat.add_user_message(other[-1]["content"])

        chunks: list[str] = []
        self.model.act(
            chat,
            tools=[t.fn for t in tools],
            on_prediction_fragment=lambda fragment, round_index=0: chunks.append(fragment.content),
            config={
                "maxTokens": self.max_tokens,
                "temperature": self.temperature,
                "toolSchemas": [t.schema for t in tools],
            },
        )
        return "".join(chunks)
