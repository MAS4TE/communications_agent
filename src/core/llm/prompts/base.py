"""Base prompt class."""

from typing import Dict, List, Optional

class BasePrompt:
    """Base class for all prompts."""
    
    def __init__(self, system_message: str, examples: Optional[List[Dict[str, str]]] = None):
        """
        Initialize a prompt.
        
        Args:
            system_message: The system message that defines the assistant's role and capabilities
            examples: Optional list of few-shot examples in the format [{"user": "...", "assistant": "..."}]
        """
        self.system_message = system_message
        self.examples = examples or []
        
    def get_messages(self) -> List[Dict[str, str]]:
        """
        Get the full prompt messages including system message and examples.
        
        Returns:
            List of message dictionaries in the format required by the LLM
        """
        messages = [{"role": "system", "content": self.system_message}]
        
        # Add any few-shot examples
        for example in self.examples:
            messages.extend([
                {"role": "user", "content": example["user"]},
                {"role": "assistant", "content": example["assistant"]}
            ])
            
        return messages