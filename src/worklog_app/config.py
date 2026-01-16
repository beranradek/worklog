"""Configuration management using Pydantic Settings."""

from functools import lru_cache
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",  # Ignore extra fields (e.g., user JIRA config in .env)
    )

    # Application settings
    app_name: str = "Worklog App"
    app_env: str = "development"
    debug: bool = False
    host: str = "0.0.0.0"
    port: int = 8000
    workers: int = 2

    # Supabase settings (required)
    supabase_url: str
    supabase_publishable_key: str
    supabase_service_role_key: Optional[str] = None

    # JWT settings for token validation
    jwt_secret: Optional[str] = None  # If not set, uses Supabase's public key

    # CORS settings
    cors_origins: str = "*"  # Comma-separated list of allowed origins

    # Frontend URL for OAuth redirect
    frontend_url: str = "http://localhost:3000"

    # Azure settings (optional, for deployment info)
    azure_subscription_id: Optional[str] = None
    azure_resource_group: Optional[str] = None
    azure_app_name: Optional[str] = None

    @property
    def cors_origins_list(self) -> list[str]:
        """Parse CORS origins into a list."""
        if self.cors_origins == "*":
            return ["*"]
        return [origin.strip() for origin in self.cors_origins.split(",")]

    @property
    def is_production(self) -> bool:
        """Check if running in production mode."""
        return self.app_env.lower() == "production"


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
