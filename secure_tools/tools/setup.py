"""
Tool Setup - Registers tools with the Secrets Broker.

This module connects tool definitions to their executors and
specifies which secrets each tool needs.
"""

from ..secrets_broker import SecretReference, SecretsBroker
from .executors import TOOL_EXECUTORS


def setup_tools(broker: SecretsBroker, vault: str = "SecureTools"):
    """
    Register all tools with the secrets broker.

    Args:
        broker: The SecretsBroker instance
        vault: The 1Password vault name containing secrets
    """

    # Weather tool - needs API key
    broker.register_tool(
        name="get_current_weather",
        executor=TOOL_EXECUTORS["get_current_weather"],
        secrets=[SecretReference(vault=vault, item="WeatherAPI", field="api_key")],
    )

    # Protected status tool - needs auth token
    broker.register_tool(
        name="get_protected_status",
        executor=TOOL_EXECUTORS["get_protected_status"],
        secrets=[SecretReference(vault=vault, item="InternalAPI", field="auth_token")],
    )

    # List services - no secrets needed
    broker.register_tool(
        name="list_available_services",
        executor=TOOL_EXECUTORS["list_available_services"],
        secrets=[],
    )
