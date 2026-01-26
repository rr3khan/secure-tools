"""
Tool Configuration Loader - Load tools from YAML config.

This module decouples tool definitions from code, making tools
more modular and configurable without code changes.
"""

from importlib import resources
from pathlib import Path

import yaml
from pydantic import BaseModel, Field

from ..secrets_broker import SecretReference, SecretsBroker
from . import register_tool, tool_registry
from .executors import TOOL_EXECUTORS


class SecretConfig(BaseModel):
    """Secret reference configuration from YAML."""

    item: str
    field: str = "password"


class ToolConfig(BaseModel):
    """Tool configuration from YAML."""

    description: str
    executor: str
    parameters: dict
    secrets: list[SecretConfig] = Field(default_factory=list)


class ToolsConfig(BaseModel):
    """Root configuration for tools.yml."""

    tools: dict[str, ToolConfig]


def _get_default_config_content() -> str:
    """Load the default tools.yml from package resources."""
    # Use importlib.resources to load config from within the package
    # This works whether running from source or installed as a package
    return resources.files("secure_tools.tool_configs").joinpath("tools.yml").read_text()


def load_tools_config(config_path: Path | None = None) -> ToolsConfig:
    """
    Load tools configuration from YAML file.

    Args:
        config_path: Path to tools.yml. If None, loads the default
                    config from the package (secure_tools/config/tools.yml)

    Returns:
        Validated ToolsConfig object

    Raises:
        FileNotFoundError: If config file doesn't exist
        ValueError: If config is invalid
    """
    if config_path is not None:
        # Load from explicit path
        if not config_path.exists():
            raise FileNotFoundError(f"Tools config not found: {config_path}")
        with open(config_path) as f:
            raw_config = yaml.safe_load(f)
    else:
        # Load from package resources (default)
        content = _get_default_config_content()
        raw_config = yaml.safe_load(content)

    return ToolsConfig(**raw_config)


def setup_tools_from_config(
    broker: SecretsBroker,
    vault: str = "SecureTools",
    config_path: Path | None = None,
) -> list[str]:
    """
    Load tool definitions from YAML and register with the secrets broker.

    Args:
        broker: The SecretsBroker instance
        vault: The 1Password vault name containing secrets
        config_path: Path to tools.yml (optional)

    Returns:
        List of registered tool names
    """
    config = load_tools_config(config_path)
    registered_tools: list[str] = []

    for tool_name, tool_config in config.tools.items():
        # Validate executor exists
        if tool_config.executor not in TOOL_EXECUTORS:
            raise ValueError(
                f"Unknown executor '{tool_config.executor}' for tool '{tool_name}'. "
                f"Available: {list(TOOL_EXECUTORS.keys())}"
            )

        # Register tool definition (for LLM)
        register_tool(
            name=tool_name,
            description=tool_config.description,
            parameters=tool_config.parameters,
        )

        # Build secret references
        secret_refs = [
            SecretReference(vault=vault, item=secret.item, field=secret.field)
            for secret in tool_config.secrets
        ]

        # Register with secrets broker (for execution)
        broker.register_tool(
            name=tool_name,
            executor=TOOL_EXECUTORS[tool_config.executor],
            secrets=secret_refs if secret_refs else None,
        )

        registered_tools.append(tool_name)

    return registered_tools


def clear_tool_registry() -> None:
    """Clear the tool registry. Useful for testing."""
    tool_registry.clear()
