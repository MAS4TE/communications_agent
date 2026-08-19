"""Pick and build the configured chat backend.

This replaces the old class-registry LLMFactory: it's just a function that
reads config.LLM_BACKEND and returns the matching ChatLLM. Add a backend by
adding a branch here and an entry to config.LLM_CONFIGS.

Two rules keep a missing LLM from taking the whole agent down:

  - "auto" (the default) picks the configured cloud backend when its API key is
    present and the offline backend when it isn't.
  - the LM Studio backend is imported lazily, because its SDK is an optional
    dependency that most deployments don't install.
"""
import logging
import os

from config import LLM_BACKEND, LLM_CONFIGS
from llm.base import ChatLLM
from llm.offline import OfflineLLM
from llm.openai_compatible import OpenAICompatibleLLM

# Which backend "auto" prefers when its credentials are available.
AUTO_PREFERENCE = ["mistral", "openai"]

log = logging.getLogger("llm")


def resolve_backend(backend: str = LLM_BACKEND) -> str:
    """Turn "auto" into a concrete backend name based on what is configured."""
    if backend != "auto":
        return backend
    for candidate in AUTO_PREFERENCE:
        if os.environ.get(LLM_CONFIGS[candidate]["api_key_env"]):
            return candidate
    return "offline"


def build_llm(backend: str = LLM_BACKEND) -> ChatLLM:
    backend = resolve_backend(backend)

    if backend == "offline":
        log.warning("no API key found — using the offline backend "
                    "(chat answers from raw data; trading is unaffected)")
        return OfflineLLM()

    config = LLM_CONFIGS[backend]

    if backend == "lmstudio":
        # Imported here, not at module level: the lmstudio SDK is an optional
        # dependency (pip install -e '.[lmstudio]') and must not break startup
        # for the far more common cloud backends.
        from llm.lmstudio_backend import LMStudioLLM

        return LMStudioLLM(
            model_name=config["model_name"],
            temperature=config["temperature"],
            max_tokens=config["max_tokens"],
        )

    # "mistral" and "openai" both speak the OpenAI protocol.
    api_key = os.environ.get(config["api_key_env"])
    if not api_key:
        raise RuntimeError(
            f"LLM backend '{backend}' needs {config['api_key_env']}. Set it, put the key "
            f"file next to config.py, or use LLM_BACKEND=auto to fall back to offline."
        )

    log.info("using backend=%s model=%s", backend, config["model_name"])
    return OpenAICompatibleLLM(
        model_name=config["model_name"],
        base_url=config["base_url"],
        api_key=api_key,
        temperature=config["temperature"],
        max_tokens=config["max_tokens"],
    )
