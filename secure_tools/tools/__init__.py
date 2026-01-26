"""
Tool Registry - Defines available tools for the LLM.

Tool definitions are loaded from config/tools.yml at runtime.
The actual execution logic lives in executors.py.

IMPORTANT: Tool definitions are visible to the LLM.
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
# Populated at runtime by setup_tools() from secure_tools/tool_configs/tools.yml
# IMPORTANT: This is empty until setup_tools() is called
tool_registry: dict[str, ToolDefinition] = {}


def register_tool(name: str, description: str, parameters: dict) -> ToolDefinition:
    """Register a tool definition."""
    tool = ToolDefinition(name=name, description=description, parameters=parameters)
    tool_registry[name] = tool
    return tool
