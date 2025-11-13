from typing import Dict, Any, Type
from pathlib import Path
import yaml


from .interfaces.base import BaseLLM
from .interfaces.agent import AgentLLM
from .backends.openai_agent import OpenAIAgent
from .backends.lmstudio_agent import LMStudioAgent


class LLMFactory:
    """Factory to create LLM instances (plain or agentic) using registry."""

    # Registry maps name -> class
    _registry: Dict[str, Type] = {}

    @classmethod
    def register(cls, name: str, cls_type: Type) -> None:
        cls._registry[name] = cls_type

    @classmethod
    def get(cls, name: str) -> Type:
        if name not in cls._registry:
            valid = list(cls._registry.keys())
            raise ValueError(f"Unknown backend '{name}'. Valid options: {valid}")
        return cls._registry[name]

    def create_from_yaml(self, config_path: Path, agentic: bool = False) -> BaseLLM | AgentLLM:
        """Instantiate LLM from YAML config."""
        with open(config_path, "r") as f:
            config = yaml.safe_load(f)

        llm_cfg = config["llm"]
        default_model = llm_cfg.get("default", "lmstudio")
        model_config = llm_cfg[default_model]

        backend_name = model_config["name"]

        # Decide class key based on agentic flag
        class_key = f"{backend_name}-agent" if agentic else f"{backend_name}-plain"
        cls_type = self.get(class_key)

        # Instantiate class, passing model_name if exists
        model_name = model_config.get("model_name")
        if model_name:
            return cls_type(model_name)
        return cls_type()

# Agentic
LLMFactory.register("openai-agent", OpenAIAgent)
LLMFactory.register("lmstudio-agent", LMStudioAgent)
