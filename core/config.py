"""
Centralized configuration management using Pydantic Settings.

All API keys and secrets should be loaded through this module,
not via scattered os.getenv() calls in business logic.
"""

from functools import lru_cache
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables and .env file.
    
    Usage:
        from core.config import get_settings
        settings = get_settings()
        api_key = settings.google_api_key
    """
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )
    
    # Google AI / Nano Banano
    google_api_key: str = ""
    vertex_ai_project: str = ""
    vertex_ai_location: str = "us-central1"
    
    # Nano Banano model configuration
    nano_banano_model: str = "nano-banano-pro"
    
    # Telegram notifications
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""
    
    # HeyGen credentials (for automated login if needed)
    heygen_login: str = ""
    heygen_password: str = ""
    
    # External APIs
    pexels_api_key: str = ""
    openai_api_key: str = ""
    runware_api_key: str = ""
    
    # Database (optional)
    database_url: str = ""
    
    # JWT (for API auth)
    jwt_secret: str = "local-development-secret-key"
    
    # Local storage
    local_storage_path: str = "./storage"
    
    # Server configuration
    port: int = 3000
    node_env: str = "development"


@lru_cache
def get_settings() -> Settings:
    """
    Get cached application settings.
    
    Settings are loaded once and cached for performance.
    Call get_settings.cache_clear() if you need to reload.
    """
    return Settings()


def validate_required_secrets(*keys: str) -> bool:
    """
    Validate that required secrets are present.
    
    Args:
        *keys: Setting attribute names to check (e.g., "google_api_key")
        
    Returns:
        True if all secrets are present and non-empty
        
    Raises:
        ValueError: If any required secret is missing
    """
    settings = get_settings()
    missing = []
    for key in keys:
        value = getattr(settings, key, "")
        if not value or not str(value).strip():
            missing.append(key.upper())
    
    if missing:
        raise ValueError(f"Missing required secrets: {', '.join(missing)}")
    
    return True
