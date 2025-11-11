"""Prompt bank for the application."""

from .base import BasePrompt
from .battery_assistant import BATTERY_ASSISTANT_PROMPT
from .prompt_bank import PromptBank

__all__ = ['BasePrompt', 'BATTERY_ASSISTANT_PROMPT', 'PromptBank']