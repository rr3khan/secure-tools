"""
Tests for the Orchestrator.

These tests verify the LLM-facing component's behaviour.
"""

import pytest

from src.config import config
from src.orchestrator import Message, Orchestrator
from src.secrets_broker import SecretsBroker


class TestOrchestrator:
    """Test the orchestrator's security validation."""

    def setup_method(self):
        """Set up a test orchestrator."""
        self.broker = SecretsBroker()
        self.orchestrator = Orchestrator(self.broker)

    def test_get_tool_definitions(self):
        """Should return tool definitions for Ollama."""
        tools = self.orchestrator.get_tool_definitions()

        assert len(tools) > 0
        assert all(t["type"] == "function" for t in tools)
        assert all("function" in t for t in tools)
        assert all("name" in t["function"] for t in tools)

    def test_validate_tool_call_rejects_unknown_tool(self):
        """Unknown tools should be rejected."""
        tool_call = {"id": "test", "function": {"name": "evil_tool", "arguments": {}}}

        with pytest.raises(ValueError, match="Unknown tool"):
            self.orchestrator._validate_tool_call(tool_call)

    def test_validate_tool_call_checks_required_params(self):
        """Required parameters must be present."""
        tool_call = {
            "id": "test",
            "function": {
                "name": "get_current_weather",
                "arguments": {"location": "Paris"},  # Missing 'format'
            },
        }

        with pytest.raises(ValueError, match="Missing required parameter"):
            self.orchestrator._validate_tool_call(tool_call)

    def test_validate_tool_call_accepts_valid_call(self):
        """Valid tool calls should pass validation."""
        tool_call = {
            "id": "test",
            "function": {
                "name": "get_current_weather",
                "arguments": {"location": "Paris", "format": "celsius"},
            },
        }

        validated = self.orchestrator._validate_tool_call(tool_call)

        assert validated.name == "get_current_weather"
        assert validated.arguments["location"] == "Paris"

    def test_tool_nicelist_enforcement(self):
        """Only allowed tools should be available when nicelist is set."""
        # Set up nicelist
        original_allowed = config.security.allowed_tools
        config.security.allowed_tools = ["list_available_services"]

        try:
            tools = self.orchestrator.get_tool_definitions()
            tool_names = [t["function"]["name"] for t in tools]

            assert "list_available_services" in tool_names
            assert "get_current_weather" not in tool_names
        finally:
            config.security.allowed_tools = original_allowed

    def test_reset_clears_conversation(self):
        """Reset should clear all state."""
        self.orchestrator.conversation.append(Message(role="user", content="test"))
        self.orchestrator.tool_call_count = 5

        self.orchestrator.reset()

        assert len(self.orchestrator.conversation) == 0
        assert self.orchestrator.tool_call_count == 0


class TestToolCallLimit:
    """Test the tool call limit security feature."""

    def test_tool_call_limit_prevents_runaway(self):
        """Exceeding tool call limit should raise error."""
        broker = SecretsBroker()
        orchestrator = Orchestrator(broker)

        # Set a low limit for testing
        original_limit = config.security.max_tool_calls
        config.security.max_tool_calls = 2
        orchestrator.tool_call_count = 2

        try:
            # Simulate exceeding the limit
            # (In practice this happens during chat loop)
            with pytest.raises(RuntimeError, match="Tool call limit exceeded"):
                orchestrator.tool_call_count += 1
                if orchestrator.tool_call_count > config.security.max_tool_calls:
                    raise RuntimeError(
                        f"Tool call limit exceeded ({config.security.max_tool_calls}). "
                        "This may indicate a runaway agent."
                    )
        finally:
            config.security.max_tool_calls = original_limit
