"""
Configuration for the Secure Tool Runner.

All settings are centralized here for easy auditing.
"""

import os

from pydantic import BaseModel, Field


class OllamaConfig(BaseModel):
    """Ollama API configuration."""

    base_url: str = Field(default="http://localhost:11434")
    model: str = Field(default="llama3.1:8b")
    timeout: float = Field(default=120.0)


class OnePasswordConfig(BaseModel):
    """1Password configuration.

    Uses the 1Password CLI (op) for secret retrieval.
    Requires OP_SERVICE_ACCOUNT_TOKEN or interactive login.
    """

    vault: str = Field(default="SecureTools")
    # Optional: specify service account token via env
    service_account_token: str | None = Field(default=None)

    def __init__(self, **data):
        super().__init__(**data)
        if self.service_account_token is None:
            self.service_account_token = os.getenv("OP_SERVICE_ACCOUNT_TOKEN")


class SecurityConfig(BaseModel):
    """Security-related settings."""

    # Maximum number of tool calls per conversation (prevents runaway agents)
    max_tool_calls: int = Field(default=10)
    # Log tool calls for audit (never logs secrets)
    audit_logging: bool = Field(default=True)
    # Allowed tools (empty = all registered tools allowed)
    allowed_tools: list[str] = Field(default_factory=list)


class Config(BaseModel):
    """Root configuration."""

    ollama: OllamaConfig = Field(default_factory=OllamaConfig)
    onepassword: OnePasswordConfig = Field(default_factory=OnePasswordConfig)
    security: SecurityConfig = Field(default_factory=SecurityConfig)


# Global config instance
config = Config()
