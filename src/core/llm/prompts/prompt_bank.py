"""Central prompt management system."""

from typing import Dict, Optional, Type

from .base import BasePrompt
from .battery_assistant import BATTERY_ASSISTANT_PROMPT

class PromptBank:
    """
    Central manager for all application prompts.
    
    This class serves as a registry and factory for all prompts used in the application.
    It ensures consistent prompt usage across different parts of the system.
    """
    
    def __init__(self):
        """Initialize the prompt bank with default prompts."""
        self._prompts: Dict[str, BasePrompt] = {
            "battery_assistant": BATTERY_ASSISTANT_PROMPT
        }
    
    def get_prompt(self, prompt_name: str) -> Optional[BasePrompt]:
        """
        Retrieve a prompt by name.
        
        Args:
            prompt_name: The name of the prompt to retrieve
            
        Returns:
            The prompt if found, None otherwise
        """
        return self._prompts.get(prompt_name)
    
    def register_prompt(self, name: str, prompt: BasePrompt) -> None:
        """
        Register a new prompt.
        
        Args:
            name: The name to register the prompt under
            prompt: The prompt to register
        """
        self._prompts[name] = prompt
    
    def list_prompts(self) -> list[str]:
        """
        Get a list of all registered prompt names.
        
        Returns:
            List of prompt names
        """
        return list(self._prompts.keys())