"""
LifeOS Configuration

Loads settings from environment variables with sensible defaults.
"""

import os
from pathlib import Path
from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """Application settings loaded from environment."""

    # Oura API
    oura_token: str = Field(default="", alias="OURA_TOKEN")
    oura_base_url: str = "https://api.ouraring.com/v2"

    # LiteLLM / AI
    litellm_api_key: str = Field(default="", alias="LITELLM_API_KEY")
    litellm_model: str = Field(default="gpt-4o-mini", alias="LITELLM_MODEL")

    # Direct API keys (optional, LiteLLM can use these)
    anthropic_api_key: str = Field(default="", alias="ANTHROPIC_API_KEY")
    openai_api_key: str = Field(default="", alias="OPENAI_API_KEY")

    # Database
    database_url: str = Field(
        default="sqlite:///./lifeos.db",
        alias="DATABASE_URL"
    )

    # Server
    host: str = Field(default="0.0.0.0", alias="HOST")
    port: int = Field(default=8080, alias="PORT")

    # Paths
    base_dir: Path = Path(__file__).parent.parent

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"

    @property
    def db_path(self) -> Path:
        """Get the SQLite database file path."""
        if self.database_url.startswith("sqlite:///"):
            db_file = self.database_url.replace("sqlite:///", "")
            if db_file.startswith("./"):
                return self.base_dir / db_file[2:]
            return Path(db_file)
        return self.base_dir / "lifeos.db"

    def get_ai_api_key(self) -> str:
        """Get the best available API key for LiteLLM."""
        if self.litellm_api_key:
            return self.litellm_api_key
        if self.anthropic_api_key:
            return self.anthropic_api_key
        if self.openai_api_key:
            return self.openai_api_key
        return ""


# Global settings instance
settings = Settings()
