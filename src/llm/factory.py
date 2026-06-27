"""Pick and build the configured chat backend.

This replaces the old class-registry LLMFactory: it's just a function that
reads config.LLM_BACKEND and returns the matching ChatLLM. Add a backend by
adding a branch here and an entry to config.LLM_CONFIGS.
"""
import os

from config import LLM_BACKEND, LLM_CONFIGS
from llm.base import ChatLLM
from llm.lmstudio_backend import LMStudioLLM
from llm.openai_compatible import OpenAICompatibleLLM


def build_llm(backend: str = LLM_BACKEND) -> ChatLLM:
    config = LLM_CONFIGS[backend]

    if backend == "lmstudio":
        return LMStudioLLM(
            model_name=config["model_name"],
            temperature=config["temperature"],
            max_tokens=config["max_tokens"],
        )

    # "mistral" and "openai" both speak the OpenAI protocol.
    return OpenAICompatibleLLM(
        model_name=config["model_name"],
        base_url=config["base_url"],
        api_key=os.environ.get(config["api_key_env"]),
        temperature=config["temperature"],
        max_tokens=config["max_tokens"],
    )
