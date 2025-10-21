import os
from pathlib import Path
from typing import Union

from dotenv import load_dotenv

class OpenAIAuthenticator:
    """Handles loading and validating the OpenAI API key."""

    def __init__(self, env_path: Union[str, Path] = None):
        self.env_path = Path(env_path) if env_path else self._default_env_path()
        self.api_key = self._load_api_key()

    def _default_env_path(self) -> Path:
        """Locate default .env file two levels up (e.g., for notebooks)."""
        cwd = Path.cwd()
        root = cwd.parent.parent
        dotenv_path = root / ".env"
        return dotenv_path

    def _load_api_key(self) -> str:
        """Load the API key from the .env file and validate it."""
        if not self.env_path.is_file():
            raise FileNotFoundError(f"{self.env_path} not found")

        load_dotenv(self.env_path, override=True)
        api_key = os.getenv("OPENAI_API_KEY")

        if not api_key:
            raise RuntimeError("OPENAI_API_KEY not found in environment")

        os.environ["OPENAI_API_KEY"] = api_key  # ensure global access
        print(f"✅ OpenAI API key loaded (ends with: ...{api_key[-4:]})")
        return api_key
