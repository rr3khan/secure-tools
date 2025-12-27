"""
Orchestrator - The LLM-facing component.

Responsibilities:
- Sends user prompts to Ollama
- Provides tool definitions to the model
- Parses and validates tool calls
- Delegates execution to the Secrets Broker
- Returns sanitized results to the LLM

IMPORTANT: This component NEVER handles secrets directly.
"""

import httpx
from pydantic import BaseModel
from rich.console import Console

from .config import config
from .secrets_broker import SecretsBroker
from .tools import ToolCall, ToolResult, tool_registry

console = Console()


class OllamaError(Exception):
    """Base exception for Ollama-related errors."""

    pass


class OllamaConnectionError(OllamaError):
    """Failed to connect to Ollama."""

    pass


class OllamaResponseError(OllamaError):
    """Ollama returned an unexpected response."""

    pass


class Message(BaseModel):
    """A conversation message."""

    role: str  # "user", "assistant", or "tool"
    content: str
    tool_calls: list[dict] | None = None
    tool_call_id: str | None = None


class Orchestrator:
    """
    Orchestrates communication between user, LLM, and tools.

    This is the UNTRUSTED zone - it never sees secrets.
    """

    # Security-focused system prompt
    SYSTEM_PROMPT = """You are a helpful assistant with access to external tools.

CRITICAL SECURITY RULES:
1. NEVER ask users to provide API keys, passwords, tokens, or any credentials directly.
2. NEVER ask users to share secrets in the chat - this is a security violation.
3. All authentication is handled automatically through a secure secrets manager (1Password).
4. If a tool fails due to missing credentials, explain that the administrator needs to
   configure the secret in 1Password - do NOT ask the user to provide it.
5. You do not have access to view or handle credentials, they are managed by a separate
   secure system.

When a tool fails due to authentication issues, respond with:
- An explanation that the required credentials are not configured
- Advise the user to contact their administrator to set up the secret in 1Password
- NEVER suggest the user provide credentials directly to you

You have access to tools that can fetch real-time data. Use them when appropriate."""

    def __init__(self, secrets_broker: SecretsBroker):
        self.secrets_broker = secrets_broker
        self.client = httpx.Client(base_url=config.ollama.base_url, timeout=config.ollama.timeout)
        self.conversation: list[Message] = []
        self.tool_call_count = 0

    def get_tool_definitions(self) -> list[dict]:
        """Get tool definitions for Ollama in the expected format."""
        tools = []
        for name, tool in tool_registry.items():
            # Respect nicelist if configured
            if config.security.allowed_tools and name not in config.security.allowed_tools:
                continue

            tools.append(
                {
                    "type": "function",
                    "function": {
                        "name": name,
                        "description": tool.description,
                        "parameters": tool.parameters,
                    },
                }
            )
        return tools

    def _call_ollama(self, messages: list[dict], include_tools: bool = True) -> dict:
        """
        Make a request to Ollama's chat API.

        Raises:
            OllamaConnectionError: If connection to Ollama fails
            OllamaResponseError: If Ollama returns an invalid response
        """
        payload = {"model": config.ollama.model, "messages": messages, "stream": False}

        if include_tools:
            tools = self.get_tool_definitions()
            if tools:
                payload["tools"] = tools

        try:
            response = self.client.post("/api/chat", json=payload)
            response.raise_for_status()
        except httpx.ConnectError as e:
            raise OllamaConnectionError(
                f"Failed to connect to Ollama at {config.ollama.base_url}. "
                "Is Ollama running? Try: ollama serve"
            ) from e
        except httpx.TimeoutException as e:
            raise OllamaConnectionError(
                f"Ollama request timed out after {config.ollama.timeout}s. "
                "The model may be loading or the request is too complex."
            ) from e
        except httpx.HTTPStatusError as e:
            raise OllamaResponseError(
                f"Ollama returned HTTP {e.response.status_code}: {e.response.text[:200]}"
            ) from e
        except httpx.HTTPError as e:
            raise OllamaConnectionError(f"HTTP error communicating with Ollama: {e}") from e

        # Parse and validate response
        try:
            data = response.json()
        except ValueError as e:
            raise OllamaResponseError(f"Ollama returned invalid JSON: {response.text[:200]}") from e

        # Validate expected response structure
        if "message" not in data:
            keys = list(data.keys())
            console.print(f"[dim yellow]Warning: Unexpected Ollama response: {keys}[/dim yellow]")
            raise OllamaResponseError(f"Ollama response missing 'message' field. Got keys: {keys}")

        return data

    def _validate_tool_call(self, tool_call: dict) -> ToolCall:
        """
        Validate a tool call from the LLM.

        This is a critical security checkpoint:
        - Tool name must be in registry
        - Arguments must be valid
        """
        func = tool_call.get("function", {})
        name = func.get("name")
        arguments = func.get("arguments", {})
        call_id = tool_call.get("id", "unknown")

        if name not in tool_registry:
            raise ValueError(f"Unknown tool requested: {name}")

        if config.security.allowed_tools and name not in config.security.allowed_tools:
            raise ValueError(f"Tool not allowed: {name}")

        tool = tool_registry[name]

        # Validate required parameters
        required = tool.parameters.get("required", [])
        for param in required:
            if param not in arguments:
                raise ValueError(f"Missing required parameter '{param}' for tool '{name}'")

        return ToolCall(id=call_id, name=name, arguments=arguments)

    def _execute_tool(self, tool_call: ToolCall) -> ToolResult:
        """
        Execute a tool via the Secrets Broker.

        The orchestrator NEVER executes tools directly.
        All execution goes through the trusted boundary.
        """
        if config.security.audit_logging:
            console.print(f"[dim]🔧 Tool call: {tool_call.name}({tool_call.arguments})[/dim]")

        # Delegate to secrets broker (the trusted boundary)
        result = self.secrets_broker.execute_tool(tool_call)

        if config.security.audit_logging:
            # Log result summary, never the full content (might contain sensitive data)
            status = "✅" if result.success else "❌"
            console.print(f"[dim]{status} Tool result: {len(result.content)} chars[/dim]")

        return result

    def chat(self, user_message: str) -> str:
        """
        Process a user message through the full conversation loop.

        This handles the complete flow:
        1. Send user message to LLM
        2. If LLM requests tools, execute them
        3. Return tool results to LLM
        4. Repeat until LLM provides final response
        """
        # Add user message to conversation
        self.conversation.append(Message(role="user", content=user_message))

        while True:
            # Convert conversation to Ollama format, starting with system prompt
            messages = [{"role": "system", "content": self.SYSTEM_PROMPT}]
            for msg in self.conversation:
                m = {"role": msg.role, "content": msg.content}
                if msg.tool_calls:
                    m["tool_calls"] = msg.tool_calls
                if msg.tool_call_id:
                    m["tool_call_id"] = msg.tool_call_id
                messages.append(m)

            # Call Ollama (errors bubble up with clear messages)
            response = self._call_ollama(messages)

            assistant_msg = response.get("message", {})

            # Check for tool calls
            tool_calls = assistant_msg.get("tool_calls", [])

            if tool_calls:
                # Check tool call limit
                self.tool_call_count += len(tool_calls)
                if self.tool_call_count > config.security.max_tool_calls:
                    raise RuntimeError(
                        f"Tool call limit exceeded ({config.security.max_tool_calls}). "
                        "This may indicate a runaway agent."
                    )

                # Add assistant's tool call message
                self.conversation.append(
                    Message(
                        role="assistant",
                        content=assistant_msg.get("content", ""),
                        tool_calls=tool_calls,
                    )
                )

                # Execute each tool call
                for tc in tool_calls:
                    try:
                        validated_call = self._validate_tool_call(tc)
                        result = self._execute_tool(validated_call)

                        # Add tool result to conversation
                        self.conversation.append(
                            Message(
                                role="tool", content=result.content, tool_call_id=validated_call.id
                            )
                        )
                    except Exception as e:
                        # On error, still add a result so LLM can handle gracefully
                        self.conversation.append(
                            Message(
                                role="tool",
                                content=f"Error executing tool: {str(e)}",
                                tool_call_id=tc.get("id", "unknown"),
                            )
                        )

                # Continue the loop to get LLM's next response
                continue

            # No tool calls - this is the final response
            final_content = assistant_msg.get("content", "")
            self.conversation.append(Message(role="assistant", content=final_content))
            return final_content

    def reset(self):
        """Reset conversation state."""
        self.conversation = []
        self.tool_call_count = 0
