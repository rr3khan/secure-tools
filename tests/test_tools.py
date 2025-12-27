"""
Tests for tool executors.

Verifies that tools work correctly and don't leak secrets.
"""

import json

from src.tools.executors import (
    execute_get_current_weather,
    execute_get_protected_status,
    execute_list_available_services,
)


class TestWeatherTool:
    """Test the weather tool executor."""

    def test_mock_mode_without_api_key(self):
        """Should work in mock mode without API key."""
        result = execute_get_current_weather(
            arguments={"location": "Paris", "format": "celsius"},
            secrets={},  # No API key
        )

        assert result.success is True
        data = json.loads(result.content)
        assert "temperature" in data
        assert "condition" in data
        assert data["source"] == "mock_data"

    def test_celsius_format(self):
        """Celsius format should return °C."""
        result = execute_get_current_weather(
            arguments={"location": "Paris", "format": "celsius"}, secrets={}
        )

        data = json.loads(result.content)
        assert "°C" in data["temperature"]

    def test_fahrenheit_format(self):
        """Fahrenheit format should return °F."""
        result = execute_get_current_weather(
            arguments={"location": "Paris", "format": "fahrenheit"}, secrets={}
        )

        data = json.loads(result.content)
        assert "°F" in data["temperature"]

    def test_known_locations_have_weather(self):
        """Known locations should return appropriate weather."""
        locations = ["paris", "london", "tokyo", "new york", "san francisco"]

        for loc in locations:
            result = execute_get_current_weather(
                arguments={"location": loc, "format": "celsius"}, secrets={}
            )

            assert result.success is True
            data = json.loads(result.content)
            assert data["condition"] != ""

    def test_api_key_not_in_result(self):
        """API key should never appear in the result."""
        result = execute_get_current_weather(
            arguments={"location": "Paris", "format": "celsius"},
            secrets={"api_key": "secret-test-key-12345"},
        )

        assert "secret-test-key-12345" not in result.content


class TestProtectedStatusTool:
    """Test the protected status tool executor."""

    def test_returns_status_info(self):
        """Should return project status information."""
        result = execute_get_protected_status(arguments={"project": "test-project"}, secrets={})

        assert result.success is True
        data = json.loads(result.content)
        assert data["project"] == "test-project"
        assert "status" in data
        assert "protected" in data


class TestListServicesTool:
    """Test the list services tool executor."""

    def test_returns_service_list(self):
        """Should return available services."""
        result = execute_list_available_services(arguments={}, secrets={})

        assert result.success is True
        data = json.loads(result.content)
        assert "services" in data
        assert len(data["services"]) > 0

    def test_no_secrets_needed(self):
        """Should work without any secrets."""
        result = execute_list_available_services(arguments={}, secrets={})

        assert result.success is True
