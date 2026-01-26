"""
Tests for the YAML tool configuration loader.

Verifies that tools are correctly loaded from config/tools.yml.
"""

import tempfile
from pathlib import Path

import pytest

from secure_tools.secrets_broker import SecretsBroker
from secure_tools.tools import tool_registry
from secure_tools.tools.loader import (
    ToolsConfig,
    clear_tool_registry,
    load_tools_config,
    setup_tools_from_config,
)


class TestLoadToolsConfig:
    """Test YAML config loading."""

    def test_loads_default_config(self):
        """Should load the default config/tools.yml."""
        config = load_tools_config()

        assert isinstance(config, ToolsConfig)
        assert "get_current_weather" in config.tools
        assert "get_protected_status" in config.tools
        assert "list_available_services" in config.tools

    def test_weather_tool_has_correct_structure(self):
        """Weather tool should have expected fields."""
        config = load_tools_config()
        weather = config.tools["get_current_weather"]

        assert weather.description
        assert weather.executor == "get_current_weather"
        assert weather.parameters["type"] == "object"
        assert "location" in weather.parameters["properties"]
        assert len(weather.secrets) == 1
        assert weather.secrets[0].item == "WeatherAPI"
        assert weather.secrets[0].field == "api_key"

    def test_tool_without_secrets(self):
        """Tools can have empty secrets list."""
        config = load_tools_config()
        list_services = config.tools["list_available_services"]

        assert list_services.secrets == []

    def test_missing_config_raises_error(self):
        """Should raise FileNotFoundError for missing config."""
        with pytest.raises(FileNotFoundError):
            load_tools_config(Path("/nonexistent/tools.yml"))

    def test_invalid_yaml_raises_error(self):
        """Should raise error for invalid YAML."""
        import yaml

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
            f.write("invalid: yaml: content: [")
            f.flush()

            with pytest.raises(yaml.YAMLError):
                load_tools_config(Path(f.name))


class TestSetupToolsFromConfig:
    """Test tool registration from config."""

    def setup_method(self):
        """Clear registry before each test."""
        clear_tool_registry()

    def test_registers_tools_in_registry(self):
        """Should register all tools from config."""
        broker = SecretsBroker()
        registered = setup_tools_from_config(broker)

        assert "get_current_weather" in registered
        assert "get_current_weather" in tool_registry

    def test_registers_tools_with_broker(self):
        """Should register executors with the broker."""
        broker = SecretsBroker()
        setup_tools_from_config(broker)

        # Broker should have the executors
        assert "get_current_weather" in broker._executors
        assert "get_protected_status" in broker._executors

    def test_builds_secret_references_with_vault(self):
        """Should build secret refs with the provided vault."""
        broker = SecretsBroker()
        setup_tools_from_config(broker, vault="TestVault")

        # Check that secret refs were built with correct vault
        refs = broker._secret_refs.get("get_current_weather", [])
        assert len(refs) == 1
        assert refs[0].vault == "TestVault"
        assert refs[0].item == "WeatherAPI"
        assert refs[0].field == "api_key"

    def test_invalid_executor_raises_error(self):
        """Should raise error for unknown executor."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
            f.write("""
tools:
  bad_tool:
    description: "A tool with invalid executor"
    executor: "nonexistent_executor"
    parameters:
      type: object
      properties: {}
      required: []
    secrets: []
""")
            f.flush()

            broker = SecretsBroker()
            with pytest.raises(ValueError, match="Unknown executor"):
                setup_tools_from_config(broker, config_path=Path(f.name))


class TestClearToolRegistry:
    """Test registry clearing."""

    def test_clears_all_tools(self):
        """Should remove all tools from registry."""
        # First, ensure some tools are registered
        broker = SecretsBroker()
        setup_tools_from_config(broker)
        assert len(tool_registry) > 0

        # Clear and verify
        clear_tool_registry()
        assert len(tool_registry) == 0
