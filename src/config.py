"""Configuration management for Firmia MCP Server."""

from typing import Optional
from functools import lru_cache
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )
    
    # API Credentials
    insee_client_id: str = Field(..., description="INSEE API client ID")
    insee_client_secret: str = Field(..., description="INSEE API client secret")
    inpi_username: str = Field(..., description="INPI username")
    inpi_password: str = Field(..., description="INPI password")
    api_entreprise_token: str = Field(..., description="API Entreprise long-lived token")
    dgfip_client_id: Optional[str] = Field(None, description="DGFIP client ID")
    dgfip_client_secret: Optional[str] = Field(None, description="DGFIP client secret")
    
    # Infrastructure
    redis_url: str = Field("redis://localhost:6379/0", description="Redis connection URL")
    duckdb_path: str = Field("/data/analytics.db", description="DuckDB database path")
    aws_region: str = Field("eu-west-1", description="AWS region")
    aws_secrets_prefix: str = Field("fci-mcp/", description="AWS Secrets Manager prefix")
    
    # MCP Server
    mcp_host: str = Field("0.0.0.0", description="MCP server host")
    mcp_port: int = Field(8789, description="MCP server port")
    
    # Monitoring
    otel_exporter_otlp_endpoint: str = Field("http://localhost:4317", description="OpenTelemetry endpoint")
    prometheus_port: int = Field(9090, description="Prometheus metrics port")
    log_level: str = Field("INFO", description="Logging level")
    
    # Environment
    environment: str = Field("development", description="Environment name")
    
    # Rate Limiting
    rate_limit_enabled: bool = Field(True, description="Enable rate limiting")
    rate_limit_window: int = Field(60, description="Rate limit window in seconds")
    rate_limit_max_requests: int = Field(100, description="Max requests per window")
    
    # API Rate Limits (requests per minute)
    rate_limit_recherche_entreprises: int = Field(3000, description="50 req/s = 3000 req/min")
    rate_limit_insee_sirene: int = Field(30, description="30 req/min")
    rate_limit_inpi_rne: int = Field(20, description="100 req/5min = 20 req/min avg")
    rate_limit_api_entreprise_json: int = Field(250, description="250 req/min for JSON")
    rate_limit_api_entreprise_pdf: int = Field(50, description="50 req/min for PDFs")
    rate_limit_bodacc: int = Field(600, description="10 req/s = 600 req/min")
    rate_limit_rna: int = Field(10, description="10 req/min")
    rate_limit_rge: int = Field(600, description="No specific limit, using 10 req/s")
    rate_limit_ficoba: int = Field(200, description="200 req/min")
    
    # Cache TTLs (in seconds)
    cache_ttl_search: int = Field(300, description="Search results cache TTL (5 minutes)")
    cache_ttl_company: int = Field(3600, description="Company profile cache TTL (1 hour)")
    cache_ttl_document: int = Field(86400, description="Document cache TTL (24 hours)")
    
    # Circuit Breaker
    circuit_breaker_failure_threshold: int = Field(5, description="Failures before opening circuit")
    circuit_breaker_recovery_timeout: int = Field(60, description="Recovery timeout in seconds")
    circuit_breaker_expected_exception: str = Field("HTTPError", description="Expected exception type")
    
    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        """Validate log level."""
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if v.upper() not in valid_levels:
            raise ValueError(f"Invalid log level: {v}. Must be one of {valid_levels}")
        return v.upper()
    
    @field_validator("environment")
    @classmethod
    def validate_environment(cls, v: str) -> str:
        """Validate environment."""
        valid_envs = ["development", "staging", "production"]
        if v.lower() not in valid_envs:
            raise ValueError(f"Invalid environment: {v}. Must be one of {valid_envs}")
        return v.lower()
    
    @property
    def is_production(self) -> bool:
        """Check if running in production environment."""
        return self.environment == "production"
    
    @property
    def is_development(self) -> bool:
        """Check if running in development environment."""
        return self.environment == "development"


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


# Convenience export
settings = get_settings()