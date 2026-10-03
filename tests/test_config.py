"""Tests for configuration and LLM connection."""

import os
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from src.config.settings import Settings, settings


def test_settings_load():
    """Test that settings can be loaded."""
    assert settings is not None
    assert isinstance(settings, Settings)
    assert settings.LLM_PROVIDER in ("nvidia", "openai")


def test_get_llm_config():
    """Test LLM config returns correct structure."""
    config = settings.get_llm_config()
    assert "api_key" in config
    assert "model" in config
    assert "temperature" in config
    assert "base_url" in config


def test_nvidia_config_defaults():
    """Test NVIDIA config has expected defaults when provider is nvidia."""
    if settings.LLM_PROVIDER == "nvidia":
        config = settings.get_llm_config()
        assert config["base_url"] == "https://integrate.api.nvidia.com/v1"
        assert config["model"] == "nvidia/nemotron-3-ultra-550b-a55b"
        assert config["temperature"] == 0.6


def test_validate_method():
    """Test validate method returns list of errors."""
    errors = settings.validate()
    assert isinstance(errors, list)


if __name__ == "__main__":
    test_settings_load()
    test_get_llm_config()
    test_nvidia_config_defaults()
    test_validate_method()
    print("All config tests passed!")