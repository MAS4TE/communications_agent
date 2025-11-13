"""Application settings."""
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # OpenAI Configuration
    OPENAI_API_KEY: str | None = None
    
    # LLM Configuration
    LLM_CONFIG_PATH: str = "src/configs/config_openai.yaml"
    
    # URLs and Endpoints
    CHRONOS_URL: str = "http://127.0.0.1:8000"
    CHRONOS_TIMEOUT: int = 15

    # Log Paths
    CPU_LOG_PATH: str = "../../data/cpu_history"
    
    class Config:
        """Pydantic configuration."""
        env_file = ".env"
        env_file_encoding = "utf-8"