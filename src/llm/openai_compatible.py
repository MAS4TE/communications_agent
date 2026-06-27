"""Chat backend for any OpenAI-compatible API.

Both Mistral and OpenAI speak the same protocol, so one class covers both — it
only differs by base URL, model name and API key (see config.LLM_CONFIGS and
llm/factory.py). LM Studio is different enough to need its own backend
(see lmstudio_backend.py).
"""
import json

from openai import OpenAI

from llm.base import ChatLLM, Tool, recent_messages


class OpenAICompatibleLLM(ChatLLM):
    def __init__(self, model_name: str, base_url: str | None, api_key: str | None,
                 temperature: float = 0.0, max_tokens: int = 1000):
        self.model_name = model_name
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.client = OpenAI(api_key=api_key, base_url=base_url)

    def invoke(self, messages: list[dict], tools: list[Tool]) -> str:
        schemas = [t.schema for t in tools]
        fn_by_name = {t.name: t.fn for t in tools}
        conversation = recent_messages(messages)

        # Tool-calling loop: keep going until the model answers without a tool call.
        while True:
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=conversation,
                tools=schemas,
                tool_choice="auto",
                temperature=self.temperature,
                max_tokens=self.max_tokens,
            )
            message = response.choices[0].message

            if not message.tool_calls:
                return message.content or ""

            # Record the assistant's request to call tools.
            conversation.append({
                "role": "assistant",
                "content": message.content,
                "tool_calls": [
                    {
                        "id": call.id,
                        "type": "function",
                        "function": {
                            "name": call.function.name,
                            "arguments": call.function.arguments,
                        },
                    }
                    for call in message.tool_calls
                ],
            })

            # Run each requested tool and feed the result back in.
            for call in message.tool_calls:
                fn = fn_by_name.get(call.function.name)
                if fn is None:
                    result = f"Tool '{call.function.name}' not found."
                else:
                    result = fn(**json.loads(call.function.arguments))
                conversation.append({
                    "role": "tool",
                    "tool_call_id": call.id,
                    "content": str(result),
                })
