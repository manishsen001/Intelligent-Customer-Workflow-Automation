"""Configuration management for the AI Workflow Automation System."""

import os
from pathlib import Path

from dotenv import load_dotenv

# Load environment variables from .env file
env_path = Path(__file__).parent.parent.parent / ".env"
load_dotenv(dotenv_path=env_path)


class Settings:
    """Application settings loaded from environment variables."""

    # LLM Provider
    LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "nvidia").lower()

    # NVIDIA API
    NVIDIA_API_KEY: str = os.getenv("NVIDIA_API_KEY", "")
    NVIDIA_BASE_URL: str = os.getenv("NVIDIA_BASE_URL", "https://integrate.api.nvidia.com/v1")
    NVIDIA_MODEL: str = os.getenv("NVIDIA_MODEL", "nvidia/nemotron-3-ultra-550b-a55b")

    # OpenAI API (legacy support)
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    OPENAI_TEMPERATURE: float = float(os.getenv("OPENAI_TEMPERATURE", "0.7"))

    # Email
    SMTP_SERVER: str = os.getenv("SMTP_SERVER", "smtp.gmail.com")
    SMTP_PORT: int = int(os.getenv("SMTP_PORT", "587"))
    EMAIL_ADDRESS: str = os.getenv("EMAIL_ADDRESS", "")
    EMAIL_PASSWORD: str = os.getenv("EMAIL_PASSWORD", "")

    # Database
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///workflow.db")

    # Logging
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    LOG_FILE: str = os.getenv("LOG_FILE", "logs/app.log")

    # Streamlit
    STREAMLIT_SERVER_PORT: int = int(os.getenv("STREAMLIT_SERVER_PORT", "8501"))
    STREAMLIT_SERVER_ADDRESS: str = os.getenv("STREAMLIT_SERVER_ADDRESS", "localhost")

    # Paths
    BASE_DIR: Path = Path(__file__).parent.parent.parent
    LOGS_DIR: Path = BASE_DIR / "logs"
    DATA_DIR: Path = BASE_DIR / "data"

    def __init__(self):
        """Initialize directories."""
        self.LOGS_DIR.mkdir(exist_ok=True)
        self.DATA_DIR.mkdir(exist_ok=True)

    def get_llm_config(self) -> dict:
        """Get LLM configuration based on provider."""
        if self.LLM_PROVIDER == "nvidia":
            return {
                "api_key": self.NVIDIA_API_KEY,
                "base_url": self.NVIDIA_BASE_URL,
                "model": self.NVIDIA_MODEL,
                "temperature": 0.6,
            }
        elif self.LLM_PROVIDER == "openai":
            return {
                "api_key": self.OPENAI_API_KEY,
                "base_url": None,
                "model": self.OPENAI_MODEL,
                "temperature": self.OPENAI_TEMPERATURE,
            }
        else:
            raise ValueError(f"Unsupported LLM_PROVIDER: {self.LLM_PROVIDER}")

    def validate(self) -> list[str]:
        """Validate required settings."""
        errors = []
        llm_config = self.get_llm_config()
        if not llm_config.get("api_key"):
            errors.append(f"{self.LLM_PROVIDER.upper()}_API_KEY is required")
        if not self.EMAIL_ADDRESS:
            errors.append("EMAIL_ADDRESS is required for email automation")
        if not self.EMAIL_PASSWORD:
            errors.append("EMAIL_PASSWORD is required for email automation")
        return errors


settings = Settings()