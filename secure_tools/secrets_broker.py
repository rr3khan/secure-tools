"""
Secrets Broker - The Trusted Execution Boundary.

This is the ONLY component that may:
- Access 1Password
- Handle credentials
- Execute authenticated requests

All secrets stay within this boundary. Results are sanitized
before being returned to the orchestrator.
"""

import os
import subprocess
from collections.abc import Callable

from pydantic import BaseModel
from rich.console import Console

from .config import config
from .tools import ToolCall, ToolResult

console = Console()

# Timeout for 1Password CLI operations
OP_CLI_TIMEOUT_SECONDS = 30


class SecretReference(BaseModel):
    """
    A reference to a secret, supporting multiple sources.

    Sources (checked in order):
    1. Environment variable (env_var) - for 1Password Environments, CI/CD, Docker
    2. 1Password CLI (vault/item/field) - traditional op:// references

    Examples:
        - env_var only: SecretReference(env_var="WEATHER_API_KEY", field="api_key")
        - 1Password only: SecretReference(vault="V", item="I", field="api_key")
        - Both (env preferred): SecretReference(env_var="KEY", vault="V", item="I", field="f")
    """

    # Environment variable name (checked first)
    env_var: str | None = None
    # 1Password reference (fallback)
    vault: str | None = None
    item: str | None = None
    field: str = "password"

    @property
    def uri(self) -> str | None:
        """1Password URI, or None if not configured."""
        if self.vault and self.item:
            return f"op://{self.vault}/{self.item}/{self.field}"
        return None

    @property
    def has_op_reference(self) -> bool:
        """Whether this has a 1Password reference configured."""
        return self.vault is not None and self.item is not None

    @property
    def has_env_var(self) -> bool:
        """Whether this has an environment variable configured."""
        return self.env_var is not None


# Type alias for tool execution functions
ToolExecutor = Callable[[dict, dict], ToolResult]


class SecretsBroker:
    """
    The trusted boundary for secret management and tool execution.

    This component:
    1. Retrieves secrets from 1Password
    2. Executes tools with those secrets
    3. Scrubs outputs to prevent secret leakage
    4. Returns only safe, minimal results

    SECURITY: Secrets never leave this component.
    """

    def __init__(self, require_secrets: bool = False):
        """
        Initialize the secrets broker.

        Args:
            require_secrets: If True, fail when secrets can't be fetched.
                           If False, allow tools to run in mock mode.
        """
        self.require_secrets = require_secrets
        # Map of tool names to their executors
        self._executors: dict[str, ToolExecutor] = {}
        # Map of tool names to their required secrets
        self._secret_refs: dict[str, list[SecretReference]] = {}
        # Cache of resolved secrets (in memory only, never logged)
        self._secret_cache: dict[str, str] = {}

    def register_tool(
        self,
        name: str,
        executor: ToolExecutor,
        secrets: list[SecretReference] | None = None,
    ):
        """
        Register a tool with the broker.

        Args:
            name: Tool name (must match registry)
            executor: Function(arguments, secrets) -> ToolResult
            secrets: List of secret references needed by this tool
        """
        self._executors[name] = executor
        if secrets:
            self._secret_refs[name] = secrets

    def _get_secret_from_env(self, ref: SecretReference) -> str | None:
        """
        Try to get secret from environment variable.

        Returns None if env_var is not configured or not set.
        """
        if not ref.has_env_var:
            return None

        value = os.environ.get(ref.env_var)
        if value:
            return value
        return None

    def _get_secret_from_op(self, ref: SecretReference) -> str:
        """
        Retrieve a secret from 1Password CLI.

        Uses the 1Password CLI (op) to fetch secrets.
        Supports both service account and interactive auth.

        SECURITY: This is the ONLY place 1Password secrets are fetched.
        """
        if not ref.has_op_reference:
            raise RuntimeError("No 1Password reference configured for this secret")

        cache_key = ref.uri

        # Check cache first
        if cache_key in self._secret_cache:
            return self._secret_cache[cache_key]

        # Build op command
        cmd = ["op", "read", ref.uri]

        # Set up environment
        env = os.environ.copy()
        if config.onepassword.service_account_token:
            env["OP_SERVICE_ACCOUNT_TOKEN"] = config.onepassword.service_account_token

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                env=env,
                timeout=OP_CLI_TIMEOUT_SECONDS,
            )

            if result.returncode != 0:
                error_msg = result.stderr.strip()
                # Never log the command output in detail (might contain hints)
                console.print("[red]Failed to retrieve secret from 1Password[/red]")
                raise RuntimeError(f"1Password CLI error: {error_msg}")

            secret = result.stdout.strip()

            # Cache it
            self._secret_cache[cache_key] = secret

            return secret

        except subprocess.TimeoutExpired:
            raise RuntimeError("1Password CLI timed out")
        except FileNotFoundError:
            raise RuntimeError(
                "1Password CLI (op) not found. Install it with: brew install 1password-cli"
            )

    def _get_secret(self, ref: SecretReference) -> str:
        """
        Retrieve a secret, trying sources in order.

        Resolution order:
        1. Environment variable (if configured)
        2. 1Password CLI (if configured)

        SECURITY: This is the ONLY place secrets are fetched.
        """
        # Try environment variable first
        if ref.has_env_var:
            env_value = self._get_secret_from_env(ref)
            if env_value:
                return env_value

        # Fall back to 1Password
        if ref.has_op_reference:
            return self._get_secret_from_op(ref)

        # Neither configured
        raise RuntimeError(
            f"No secret source configured for field '{ref.field}'. "
            "Set either env_var or vault/item in tools.yml."
        )

    def _resolve_secrets(self, tool_name: str) -> dict[str, str]:
        """
        Resolve all secrets needed by a tool.

        Returns a dict mapping field names to secret values.

        Resolution order for each secret:
        1. Environment variable (if configured)
        2. 1Password CLI (if configured)

        Behavior depends on require_secrets:
        - If False: returns empty dict on failure (mock mode)
        - If True: raises an error if secrets can't be fetched
        """
        secrets = {}
        refs = self._secret_refs.get(tool_name, [])

        for ref in refs:
            try:
                # Try to get the secret (env var first, then 1Password)
                secret_value = self._get_secret(ref)
                secrets[ref.field] = secret_value

                # Log which source was used
                if ref.has_env_var and os.environ.get(ref.env_var):
                    console.print(f"[green]🔑 Secret loaded from env: {ref.env_var}[/green]")
                elif ref.has_op_reference:
                    console.print(
                        f"[green]🔑 Secret loaded from 1Password: {ref.item}/{ref.field}[/green]"
                    )

            except Exception as e:
                # Determine the secret identifier for error messages
                secret_id = ref.env_var if ref.has_env_var else f"{ref.item}/{ref.field}"

                if self.require_secrets:
                    # Live mode - secrets are required
                    console.print(f"[red]✗ Secret required: {secret_id}[/red]")
                    raise RuntimeError(
                        f"Secret '{secret_id}' is required but unavailable. "
                        f"Set the environment variable or configure 1Password."
                    ) from e
                else:
                    # Mock mode - continue without secret
                    console.print(
                        f"[yellow]⚠ Secret unavailable: {secret_id} - mock mode[/yellow]"
                    )

        return secrets

    def _scrub_output(self, content: str, secrets: dict[str, str]) -> str:
        """
        Remove any secrets that might have leaked into the output.

        This is a defense-in-depth measure. Ideally, tool executors
        should never include secrets in their output, but we scrub
        anyway as a safety net.

        SECURITY: Critical for preventing accidental secret exposure.
        """
        scrubbed = content
        for secret in secrets.values():
            if secret:
                scrubbed = scrubbed.replace(secret, "[REDACTED]")
        return scrubbed

    def execute_tool(self, call: ToolCall) -> ToolResult:
        """
        Execute a tool call securely.

        Flow:
        1. Look up the tool executor
        2. Resolve required secrets from 1Password
        3. Execute the tool with secrets
        4. Scrub output to prevent leakage
        5. Return sanitized result
        """
        if call.name not in self._executors:
            return ToolResult(
                success=False,
                content=f"Tool '{call.name}' not registered with secrets broker",
            )

        executor = self._executors[call.name]

        try:
            # Step 1: Resolve secrets (stays in this boundary)
            secrets = self._resolve_secrets(call.name)

            # Step 2: Execute the tool
            result = executor(call.arguments, secrets)

            # Step 3: Scrub output before returning
            result.content = self._scrub_output(result.content, secrets)

            return result

        except Exception as e:
            # Never expose internal errors that might hint at secrets
            error_msg = str(e)
            # Scrub the error message too
            if self._secret_refs.get(call.name):
                secrets = {
                    ref.field: self._secret_cache.get(ref.uri, "")
                    for ref in self._secret_refs[call.name]
                }
                error_msg = self._scrub_output(error_msg, secrets)

            return ToolResult(success=False, content=f"Tool execution failed: {error_msg}")

    def clear_cache(self):
        """Clear the secret cache. Call this when done with a session."""
        self._secret_cache.clear()
