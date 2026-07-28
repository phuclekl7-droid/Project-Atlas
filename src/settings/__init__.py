"""
Settings module: Manages application configuration and environment variables.
Supports loading from .env files and config.json with sensible defaults.
"""

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

from src.core import ConfigurationError, setup_logger
from src.core.encryption import Encryptor

logger = setup_logger("settings")

# Default paths
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_ENV_PATH = PROJECT_ROOT / ".env"
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "config.json"

# Provider constants
PROVIDER_OLLAMA = "ollama"
PROVIDER_OPENAI = "openai"
PROVIDER_GEMINI = "gemini"
PROVIDER_MOCK = "mock"

SUPPORTED_PROVIDERS = {
    PROVIDER_MOCK,
    PROVIDER_OLLAMA,
    PROVIDER_OPENAI,
    PROVIDER_GEMINI,
}


@dataclass
class Settings:
    """
    Application settings loaded from environment and config file.

    Attributes:
        model_provider: LLM provider name (ollama, openai, gemini, mock)
        ollama_url: Base URL for Ollama server
        ollama_model: Default Ollama model name
        openai_api_key: OpenAI API key
        openai_model: Default OpenAI model name
        gemini_api_key: Google Gemini API key
        gemini_model: Default Gemini model name
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR)
        memory_path: Path to SQLite memory database file
        max_context_messages: Number of recent messages to include as context
        config_path: Path to JSON config file (read-only)
    """

    # Model provider
    model_provider: str = PROVIDER_MOCK

    # Ollama
    ollama_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.2:1b"

    # OpenAI
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"

    # Gemini
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.0-flash"

    # Weather
    weather_api_key: str = ""

    # System
    log_level: str = "INFO"
    memory_path: str = str(PROJECT_ROOT / "data" / "memory.db")
    max_context_messages: int = 10

    # Token & Rate Limiting
    max_context_tokens: int = 4096  # Max estimated tokens for context pruning
    rate_limit_requests: int = 60   # Max API requests per minute (0 = unlimited)
    rate_limit_tokens: int = 100000  # Max tokens per minute (0 = unlimited, e.g. GPT-4o-mini tier)

    # Multi-Model Routing
    multi_model_enabled: bool = False  # Auto-route messages to best provider

    # Internal
    config_path: Path = field(default_factory=lambda: DEFAULT_CONFIG_PATH, repr=False)

    def validate(self) -> None:
        """Validate current settings and raise ConfigurationError if invalid."""
        if self.model_provider not in SUPPORTED_PROVIDERS:
            raise ConfigurationError(
                f"Unsupported model provider: '{self.model_provider}'. "
                f"Supported: {', '.join(sorted(SUPPORTED_PROVIDERS))}"
            )

        if self.model_provider == PROVIDER_OPENAI and not self.openai_api_key:
            raise ConfigurationError(
                "OpenAI provider selected but OPENAI_API_KEY is not set. "
                "Add it to your .env file."
            )

        if self.model_provider == PROVIDER_GEMINI and not self.gemini_api_key:
            raise ConfigurationError(
                "Gemini provider selected but GEMINI_API_KEY is not set. "
                "Add it to your .env file."
            )

    def to_dict(self) -> dict:
        """Export settings as a dict (safe version without secrets)."""
        return {
            "model_provider": self.model_provider,
            "ollama_url": self.ollama_url,
            "ollama_model": self.ollama_model,
            "openai_model": self.openai_model,
            "gemini_model": self.gemini_model,
            "log_level": self.log_level,
            "memory_path": self.memory_path,
            "max_context_messages": self.max_context_messages,
            "max_context_tokens": self.max_context_tokens,
            "rate_limit_requests": self.rate_limit_requests,
            "rate_limit_tokens": self.rate_limit_tokens,
        }

    def __repr__(self) -> str:
        safe = self.to_dict()
        safe["openai_api_key"] = "***" if self.openai_api_key else ""
        safe["gemini_api_key"] = "***" if self.gemini_api_key else ""
        items = ",\n  ".join(f"{k}={v!r}" for k, v in safe.items())
        return f"Settings(\n  {items}\n)"


def _load_json_config(config_path: Path) -> dict:
    """Load settings from a JSON config file, returning an empty dict if not found."""
    if not config_path.exists():
        return {}
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        logger.warning(f"Failed to load config file {config_path}: {e}")
        return {}


def _safe_int(raw: str, default: int) -> int:
    """Parse an integer string, falling back to default on error."""
    try:
        return int(raw)
    except (ValueError, TypeError):
        logger.warning(f"Invalid integer value {raw!r}, using default {default}")
        return default


def load_settings(
    env_path: Optional[Path] = None,
    config_path: Optional[Path] = None,
) -> Settings:
    """
    Load and return application Settings.

    Priority (highest to lowest):
      1. Environment variables (already set in OS)
      2. .env file variables
      3. config.json values
      4. Hardcoded defaults in Settings dataclass

    Args:
        env_path: Path to .env file (default: PROJECT_ROOT/.env)
        config_path: Path to config.json (default: PROJECT_ROOT/config.json)

    Returns:
        Configured Settings instance
    """
    env_path = env_path or DEFAULT_ENV_PATH
    config_path = config_path or DEFAULT_CONFIG_PATH

    # Step 1: Load .env file (does NOT override existing env vars)
    if env_path.exists():
        load_dotenv(dotenv_path=env_path, override=False)
        logger.debug(f"Loaded environment from {env_path}")
    else:
        logger.debug(f"No .env file found at {env_path}, using system env vars")

    # Step 2: Load JSON config
    json_config = _load_json_config(config_path)
    if json_config:
        logger.debug(f"Loaded config from {config_path}")

    # Step 3: Decrypt encrypted values via Encryptor (Feature 73)
    encryptor = Encryptor(key_file=str(Path(Settings.memory_path).parent / ".secret.key"))

    def _get_env(key: str, default: str = "") -> str:
        """Get env value and transparently decrypt if encrypted."""
        raw = os.environ.get(key, json_config.get(key.lower(), default))
        if raw.startswith("$aes$") or raw.startswith("$b64$"):
            return encryptor.decrypt(raw)
        return raw

    # Step 4: Read with priority: env var > json config > default
    get_env = lambda key, default="": _get_env(key, default)

    settings = Settings(
        model_provider=get_env("MODEL_PROVIDER", Settings.model_provider),
        ollama_url=get_env("OLLAMA_URL", Settings.ollama_url),
        ollama_model=get_env("OLLAMA_MODEL", Settings.ollama_model),
        openai_api_key=get_env("OPENAI_API_KEY", Settings.openai_api_key),
        openai_model=get_env("OPENAI_MODEL", Settings.openai_model),
        gemini_api_key=get_env("GEMINI_API_KEY", Settings.gemini_api_key),
        gemini_model=get_env("GEMINI_MODEL", Settings.gemini_model),
        weather_api_key=get_env("WEATHER_API_KEY", Settings.weather_api_key),
        log_level=get_env("LOG_LEVEL", Settings.log_level),
        memory_path=get_env("MEMORY_PATH", Settings.memory_path),
        max_context_messages=_safe_int(
            get_env("MAX_CONTEXT_MESSAGES", str(Settings.max_context_messages)),
            Settings.max_context_messages,
        ),
        max_context_tokens=_safe_int(
            get_env("MAX_CONTEXT_TOKENS", str(Settings.max_context_tokens)),
            Settings.max_context_tokens,
        ),
        rate_limit_requests=_safe_int(
            get_env("RATE_LIMIT_REQUESTS", str(Settings.rate_limit_requests)),
            Settings.rate_limit_requests,
        ),
        rate_limit_tokens=_safe_int(
            get_env("RATE_LIMIT_TOKENS", str(Settings.rate_limit_tokens)),
            Settings.rate_limit_tokens,
        ),
        config_path=config_path,
    )

    settings.validate()
    return settings
