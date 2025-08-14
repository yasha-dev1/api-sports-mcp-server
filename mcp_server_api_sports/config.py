"""Configuration management for API-Sports MCP Server."""


from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # API-Sports Configuration
    api_sports_api_key: str = Field(default="", description="API-Sports API key")
    api_sports_base_url: str = Field(
        default="https://v3.football.api-sports.io",
        description="API-Sports base URL"
    )

    # Logging Configuration
    log_level: str = Field(default="INFO", description="Logging level")
    log_file_path: str = Field(
        default="logs/api_sports_mcp.log",
        description="Log file path"
    )
    log_rotation_size: str = Field(default="10MB", description="Log rotation size")
    log_retention_days: int = Field(default=7, description="Log retention in days")
    log_format: str = Field(
        default="json",
        description="Log format (json or text)",
        pattern="^(json|text)$"
    )

    # Cache Configuration
    cache_enabled: bool = Field(default=True, description="Enable caching")
    cache_ttl_teams: int = Field(default=86400, description="Teams cache TTL in seconds")
    cache_ttl_fixtures_completed: int = Field(
        default=0,
        description="Completed fixtures cache TTL (0 = permanent)"
    )
    cache_ttl_fixtures_upcoming: int = Field(
        default=3600,
        description="Upcoming fixtures cache TTL in seconds"
    )
    cache_ttl_statistics: int = Field(
        default=3600,
        description="Statistics cache TTL in seconds"
    )
    cache_ttl_standings: int = Field(
        default=1800,
        description="Standings cache TTL in seconds"
    )
    cache_ttl_predictions: int = Field(
        default=3600,
        description="Predictions cache TTL in seconds"
    )
    cache_max_size: int = Field(default=1000, description="Maximum cache size")

    # Rate Limiting Configuration
    rate_limit_calls_per_minute: int = Field(
        default=30,
        description="API calls per minute"
    )
    rate_limit_calls_per_day: int = Field(
        default=100,
        description="API calls per day"
    )
    rate_limit_burst_size: int = Field(default=10, description="Burst size for rate limiting")
    rate_limit_backoff_factor: float = Field(
        default=2.0,
        description="Exponential backoff factor"
    )
    rate_limit_max_retries: int = Field(default=3, description="Maximum retry attempts")

    # MCP Server Configuration
    mcp_server_name: str = Field(
        default="api-sports-mcp-server",
        description="MCP server name"
    )
    mcp_server_version: str = Field(default="0.1.0", description="MCP server version")

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        """Validate log level."""
        valid_levels = ["TRACE", "DEBUG", "INFO", "SUCCESS", "WARNING", "ERROR", "CRITICAL"]
        if v.upper() not in valid_levels:
            raise ValueError(f"Invalid log level: {v}. Must be one of {valid_levels}")
        return v.upper()


# Global settings instance
settings: Settings | None = None


def get_settings() -> Settings:
    """Get or create settings instance."""
    global settings
    if settings is None:
        settings = Settings()
    return settings
