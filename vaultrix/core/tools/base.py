"""Tool protocol and registry.

Every tool declares the permissions it needs.  The ``AgentLoop`` checks
permissions before invoking.
"""

from __future__ import annotations

import abc
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Type

from vaultrix.core.permissions.models import PermissionLevel, ResourceType


@dataclass
class ToolResult:
    """Standardised return from a tool invocation."""

    success: bool
    output: str = ""
    error: str = ""
    data: Dict[str, Any] = field(default_factory=dict)


class Tool(abc.ABC):
    """Abstract base class every tool must implement."""

    # ── metadata (override in subclasses) ───────────────────────────────────

    name: str = "unnamed_tool"
    description: str = ""
    # JSON-Schema-compatible dict describing parameters
    parameters_schema: Dict[str, Any] = {}

    # Permissions this tool requires (list of (resource, level) tuples)
    required_permissions: List[tuple[ResourceType, PermissionLevel]] = []

    @abc.abstractmethod
    def execute(self, **kwargs: Any) -> ToolResult:
        """Run the tool with the given keyword arguments."""

    # ── Anthropic tool-use representation ───────────────────────────────────

    def to_anthropic_tool(self) -> Dict[str, Any]:
        """Return the tool definition Anthropic expects for tool_use."""
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.parameters_schema or {"type": "object", "properties": {}},
        }


class ToolRegistry:
    """Collects tools and exposes them for the agent loop."""

    def __init__(self) -> None:
        self._tools: Dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        self._tools[tool.name] = tool

    def get(self, name: str) -> Optional[Tool]:
        return self._tools.get(name)

    def all_tools(self) -> List[Tool]:
        return list(self._tools.values())

    def to_anthropic_tools(self) -> List[Dict[str, Any]]:
        return [t.to_anthropic_tool() for t in self._tools.values()]
