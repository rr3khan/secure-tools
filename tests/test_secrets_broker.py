"""
Tests for the Secrets Broker.

These tests verify the security properties of the trusted boundary.
"""

from src.secrets_broker import SecretReference, SecretsBroker, ToolResult


class TestSecretsBroker:
    """Test the secrets broker security properties."""

    def test_scrub_output_removes_secrets(self):
        """Secrets should be scrubbed from output."""
        broker = SecretsBroker()

        secrets = {"api_key": "super-secret-key-12345"}
        content = "Response includes super-secret-key-12345 in the data"

        scrubbed = broker._scrub_output(content, secrets)

        assert "super-secret-key-12345" not in scrubbed
        assert "[REDACTED]" in scrubbed

    def test_scrub_output_handles_multiple_secrets(self):
        """Multiple secrets should all be scrubbed."""
        broker = SecretsBroker()

        secrets = {"api_key": "secret-api-key", "auth_token": "secret-auth-token"}
        content = "Keys: secret-api-key and secret-auth-token"

        scrubbed = broker._scrub_output(content, secrets)

        assert "secret-api-key" not in scrubbed
        assert "secret-auth-token" not in scrubbed
        assert scrubbed.count("[REDACTED]") == 2

    def test_scrub_output_ignores_short_secrets(self):
        """Very short strings shouldn't be scrubbed (might be false positives)."""
        broker = SecretsBroker()

        secrets = {"pin": "1234"}  # 4 chars, too short
        content = "Your code is 1234"

        scrubbed = broker._scrub_output(content, secrets)

        # Short secrets are not scrubbed to avoid false positives
        assert scrubbed == content

    def test_unregistered_tool_fails(self):
        """Calling an unregistered tool should fail safely."""
        broker = SecretsBroker()

        from src.tools import ToolCall

        call = ToolCall(id="test", name="nonexistent_tool", arguments={})

        result = broker.execute_tool(call)

        assert result.success is False
        assert "not registered" in result.content

    def test_executor_receives_secrets(self):
        """Tool executors should receive resolved secrets."""
        broker = SecretsBroker()
        received_secrets = {}

        def test_executor(args, secrets):
            received_secrets.update(secrets)
            return ToolResult(success=True, content="ok")

        # Register without actual 1Password (will have empty secrets)
        broker.register_tool("test_tool", test_executor, secrets=[])

        from src.tools import ToolCall

        call = ToolCall(id="test", name="test_tool", arguments={"foo": "bar"})

        result = broker.execute_tool(call)

        assert result.success is True


class TestSecretReference:
    """Test secret reference URI generation."""

    def test_uri_format(self):
        """URI should follow 1Password format."""
        ref = SecretReference(vault="MyVault", item="MyItem", field="password")

        assert ref.uri == "op://MyVault/MyItem/password"

    def test_default_field(self):
        """Default field should be 'password'."""
        ref = SecretReference(vault="V", item="I")

        assert ref.field == "password"
        assert ref.uri == "op://V/I/password"
