"""
Tool Registry - Defines available tools for the LLM.

Tools are defined here with their schemas. The actual execution
logic lives in the secrets broker, not here.

IMPORTANT: Tool definitions here are visible to the LLM.
Never include secrets or sensitive implementation details.
"""

from pydantic import BaseModel


class ToolCall(BaseModel):
    """A validated tool call from the LLM."""

    id: str
    name: str
    arguments: dict


class ToolResult(BaseModel):
    """Result of a tool execution."""

    success: bool
    content: str


class ToolDefinition(BaseModel):
    """Definition of a tool available to the LLM."""

    name: str
    description: str
    parameters: dict  # JSON Schema


# The tool registry - maps tool names to their definitions
tool_registry: dict[str, ToolDefinition] = {}


def register_tool(name: str, description: str, parameters: dict) -> ToolDefinition:
    """Register a tool definition."""
    tool = ToolDefinition(name=name, description=description, parameters=parameters)
    tool_registry[name] = tool
    return tool


# =============================================================================
# Tool Definitions
# =============================================================================

# Weather Tool - requires API key authentication
register_tool(
    name="get_current_weather",
    description="Get the current weather for a location. Returns temperature and conditions.",
    parameters={
        "type": "object",
        "properties": {
            "location": {
                "type": "string",
                "description": "The location to get weather for, e.g. 'Paris, France'",
            },
            "format": {
                "type": "string",
                "description": "Temperature format: 'celsius' or 'fahrenheit'",
                "enum": ["celsius", "fahrenheit"],
            },
        },
        "required": ["location", "format"],
    },
)

# Protected Status Tool - example of a tool requiring auth
register_tool(
    name="get_protected_status",
    description="Check the protected status for a project. Requires authentication.",
    parameters={
        "type": "object",
        "properties": {
            "project": {"type": "string", "description": "The project identifier to check"}
        },
        "required": ["project"],
    },
)

# Secret Vault Info Tool - example showing the LLM can ask about non-sensitive metadata
register_tool(
    name="list_available_services",
    description="List services that are available for queries. Does not expose credentials.",
    parameters={"type": "object", "properties": {}, "required": []},
)
