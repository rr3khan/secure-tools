"""
Tests for the Secrets Broker.

These tests verify the security properties of the trusted boundary.
"""

import os

import pytest

from secure_tools.secrets_broker import SecretReference, SecretsBroker, ToolResult


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

    def test_unregistered_tool_fails(self):
        """Calling an unregistered tool should fail safely."""
        broker = SecretsBroker()

        from secure_tools.tools import ToolCall

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

        from secure_tools.tools import ToolCall

        call = ToolCall(id="test", name="test_tool", arguments={"foo": "bar"})

        result = broker.execute_tool(call)

        assert result.success is True


class TestSecretReference:
    """Test secret reference configuration."""

    def test_uri_format_with_op_reference(self):
        """URI should follow 1Password format when vault/item are set."""
        ref = SecretReference(vault="MyVault", item="MyItem", field="password")

        assert ref.uri == "op://MyVault/MyItem/password"
        assert ref.has_op_reference is True

    def test_uri_none_without_op_reference(self):
        """URI should be None when no 1Password reference is configured."""
        ref = SecretReference(env_var="MY_SECRET", field="api_key")

        assert ref.uri is None
        assert ref.has_op_reference is False

    def test_default_field(self):
        """Default field should be 'password'."""
        ref = SecretReference(vault="V", item="I")

        assert ref.field == "password"
        assert ref.uri == "op://V/I/password"

    def test_env_var_only(self):
        """Should support env_var only configuration."""
        ref = SecretReference(env_var="MY_API_KEY", field="api_key")

        assert ref.has_env_var is True
        assert ref.has_op_reference is False
        assert ref.env_var == "MY_API_KEY"

    def test_both_sources(self):
        """Should support both env_var and 1Password reference."""
        ref = SecretReference(
            env_var="MY_API_KEY",
            vault="MyVault",
            item="MyItem",
            field="api_key",
        )

        assert ref.has_env_var is True
        assert ref.has_op_reference is True


class TestEnvVarSecretResolution:
    """Test secret resolution from environment variables."""

    def test_secret_from_env_var(self):
        """Should resolve secret from environment variable."""
        broker = SecretsBroker()

        # Set up env var
        os.environ["TEST_SECRET_KEY"] = "env-secret-value"

        try:
            ref = SecretReference(env_var="TEST_SECRET_KEY", field="api_key")
            secret = broker._get_secret(ref)

            assert secret == "env-secret-value"
        finally:
            del os.environ["TEST_SECRET_KEY"]

    def test_env_var_takes_priority(self):
        """Env var should take priority over 1Password when both configured."""
        broker = SecretsBroker()

        # Set up env var
        os.environ["TEST_SECRET_KEY"] = "env-value"

        try:
            # Configure both sources - env should be used
            ref = SecretReference(
                env_var="TEST_SECRET_KEY",
                vault="Vault",
                item="Item",
                field="api_key",
            )
            secret = broker._get_secret(ref)

            assert secret == "env-value"
        finally:
            del os.environ["TEST_SECRET_KEY"]

    def test_no_source_configured_raises_error(self):
        """Should raise error when no secret source is configured."""
        broker = SecretsBroker()

        ref = SecretReference(field="api_key")  # No env_var, no vault/item

        with pytest.raises(RuntimeError, match="No secret source configured"):
            broker._get_secret(ref)

    def test_resolve_secrets_uses_env_var(self):
        """_resolve_secrets should use env vars when available."""
        broker = SecretsBroker()

        os.environ["TEST_TOOL_KEY"] = "test-env-value"

        try:
            def test_executor(args, secrets):
                return ToolResult(success=True, content=f"got: {secrets.get('api_key')}")

            ref = SecretReference(env_var="TEST_TOOL_KEY", field="api_key")
            broker.register_tool("test_tool", test_executor, secrets=[ref])

            from secure_tools.tools import ToolCall

            call = ToolCall(id="test", name="test_tool", arguments={})
            result = broker.execute_tool(call)

            assert result.success is True
            assert "got: [REDACTED]" in result.content  # Value is scrubbed
        finally:
            del os.environ["TEST_TOOL_KEY"]
