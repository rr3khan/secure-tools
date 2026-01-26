"""
Tool Setup - Registers tools with the Secrets Broker.

Tools are loaded from secure_tools/tool_configs/tools.yml which defines:
- Tool name and description
- Parameter schema (JSON Schema)
- Executor key (must match a key in TOOL_EXECUTORS, e.g., "get_current_weather")
- Secret references (1Password item/field)

This decouples tool configuration from code.
"""

from pathlib import Path

from ..secrets_broker import SecretsBroker
from .loader import setup_tools_from_config


def setup_tools(
    broker: SecretsBroker,
    vault: str = "SecureTools",
    config_path: Path | None = None,
) -> list[str]:
    """
    Load and register all tools from tools.yml.

    Args:
        broker: The SecretsBroker instance
        vault: The 1Password vault name containing secrets
        config_path: Optional path to tools.yml (defaults to package resource)

    Returns:
        List of registered tool names
    """
    return setup_tools_from_config(broker, vault=vault, config_path=config_path)
