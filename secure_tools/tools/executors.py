"""
Tool Executors - The actual implementation of tools.

These functions run INSIDE the Secrets Broker's trusted boundary.
They receive:
- arguments: The LLM's requested parameters
- secrets: Resolved credentials from 1Password

SECURITY RULES:
1. Never log secrets
2. Never include secrets in return values
3. Handle errors gracefully without exposing internals
"""

from __future__ import annotations

import json

import httpx

from . import ToolResult

# Timeout for external API requests
API_REQUEST_TIMEOUT_SECONDS = 10

# =============================================================================
# Weather Tool Executor
# =============================================================================


def execute_get_current_weather(arguments: dict, secrets: dict) -> ToolResult:
    """
    Get current weather for a location.

    For testing purposes, this uses a mock implementation.
    In production, you would call a real weather API (e.g., OpenWeatherMap)
    using the API key from secrets["api_key"].

    Args:
        arguments: {"location": str, "format": "celsius"|"fahrenheit"}
        secrets: {"api_key": str} - from 1Password
    """
    location = arguments.get("location", "Unknown")
    temp_format = arguments.get("format", "celsius")
    api_key = secrets.get("api_key")

    # Check if we have the required secret
    if not api_key:
        # For testing without 1Password, use mock mode
        return _mock_weather(location, temp_format)

    # In production, call the real API
    try:
        return _real_weather_api(location, temp_format, api_key)
    except Exception:
        # Fallback to mock on API failure
        mock_content = _mock_weather(location, temp_format).content
        return ToolResult(
            success=True,
            content=f"Weather API unavailable, using cached data. {mock_content}",
        )


def _mock_weather(location: str, temp_format: str) -> ToolResult:
    """Mock weather response for testing without API keys."""
    # Simple mock data based on location
    mock_data: dict[str, dict[str, int | str]] = {
        "paris": {"temp_c": 12, "condition": "cloudy"},
        "london": {"temp_c": 8, "condition": "rainy"},
        "tokyo": {"temp_c": 18, "condition": "sunny"},
        "new york": {"temp_c": 5, "condition": "windy"},
        "san francisco": {"temp_c": 15, "condition": "foggy"},
    }

    # Normalize location for lookup
    loc_key = location.lower().split(",")[0].strip()
    data = mock_data.get(loc_key, {"temp_c": 20, "condition": "partly cloudy"})

    temp_c = data["temp_c"]
    assert isinstance(temp_c, int)
    if temp_format == "fahrenheit":
        temp = round(temp_c * 9 / 5 + 32)
        unit = "°F"
    else:
        temp = temp_c
        unit = "°C"

    result = {
        "location": location,
        "temperature": f"{temp}{unit}",
        "condition": data["condition"],
        "source": "mock_data",
    }

    return ToolResult(success=True, content=json.dumps(result))


def _real_weather_api(location: str, temp_format: str, api_key: str) -> ToolResult:
    """
    Call real weather API (OpenWeatherMap example).

    SECURITY: The api_key is used here but NEVER returned in the result.
    """
    units = "metric" if temp_format == "celsius" else "imperial"

    # OpenWeatherMap API (as an example)
    url = "https://api.openweathermap.org/data/2.5/weather"
    params = {
        "q": location,
        "appid": api_key,  # Secret - never logged or returned
        "units": units,
    }

    with httpx.Client(timeout=API_REQUEST_TIMEOUT_SECONDS) as client:
        response = client.get(url, params=params)
        response.raise_for_status()
        data = response.json()

    # Extract only non-sensitive information
    result = {
        "location": data.get("name", location),
        "temperature": f"{data['main']['temp']}{'°C' if temp_format == 'celsius' else '°F'}",
        "condition": data["weather"][0]["description"],
        "humidity": f"{data['main']['humidity']}%",
        "source": "openweathermap",
    }

    # IMPORTANT: Do not include the API key or any auth info in the result
    return ToolResult(success=True, content=json.dumps(result))


# =============================================================================
# Protected Status Tool Executor
# =============================================================================


def execute_get_protected_status(arguments: dict, secrets: dict) -> ToolResult:
    """
    Check protected status for a project.

    This is an example of a tool that requires authentication to
    access a protected internal system.

    Args:
        arguments: {"project": str}
        secrets: {"auth_token": str} - from 1Password
    """
    project = arguments.get("project", "unknown")
    auth_token = secrets.get("auth_token")

    if not auth_token:
        # Mock mode for testing
        return ToolResult(
            success=True,
            content=json.dumps(
                {
                    "project": project,
                    "status": "active",
                    "protected": True,
                    "last_check": "2025-12-25T00:00:00Z",
                    "source": "mock_data",
                }
            ),
        )

    # In production, call your internal API with auth
    # headers = {"Authorization": f"Bearer {auth_token}"}
    # response = httpx.get(f"https://internal-api/projects/{project}/status", headers=headers)

    # For now, return mock data
    return ToolResult(
        success=True,
        content=json.dumps(
            {
                "project": project,
                "status": "active",
                "protected": True,
                "last_check": "2025-12-25T00:00:00Z",
            }
        ),
    )


# =============================================================================
# List Services Tool Executor
# =============================================================================


def execute_list_available_services(arguments: dict, secrets: dict) -> ToolResult:
    """
    List available services (no secrets required).

    This demonstrates a tool that doesn't need authentication
    but still goes through the secrets broker for consistency.
    """
    services = [
        {"name": "weather", "description": "Get current weather for any location"},
        {"name": "protected_status", "description": "Check project protection status"},
    ]

    return ToolResult(success=True, content=json.dumps({"services": services}))


# =============================================================================
# Executor Registry
# =============================================================================

# Maps tool names to their executor functions
TOOL_EXECUTORS = {
    "get_current_weather": execute_get_current_weather,
    "get_protected_status": execute_get_protected_status,
    "list_available_services": execute_list_available_services,
}
