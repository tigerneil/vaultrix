"""Built-in tools shipped with Vaultrix."""

from __future__ import annotations

from typing import Any

from vaultrix.core.permissions.models import PermissionLevel, ResourceType
from vaultrix.core.tools.base import Tool, ToolResult


class ShellTool(Tool):
    name = "shell"
    description = "Execute a shell command in the sandbox and return stdout/stderr."
    parameters_schema = {
        "type": "object",
        "properties": {
            "command": {"type": "string", "description": "Command to run"},
        },
        "required": ["command"],
    }
    required_permissions = [(ResourceType.PROCESS, PermissionLevel.EXECUTE)]

    def __init__(self, sandbox_manager: Any) -> None:
        self._sandbox = sandbox_manager

    def execute(self, **kwargs: Any) -> ToolResult:
        command = kwargs.get("command", "")
        if not command:
            return ToolResult(success=False, error="No command provided")
        try:
            result = self._sandbox.execute_command(command)
            return ToolResult(
                success=result["exit_code"] == 0,
                output=result.get("stdout", ""),
                error=result.get("stderr", ""),
                data={"exit_code": result["exit_code"]},
            )
        except Exception as exc:
            return ToolResult(success=False, error=str(exc))


class FileReadTool(Tool):
    name = "file_read"
    description = "Read a file from the sandbox."
    parameters_schema = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "File path inside the sandbox"},
        },
        "required": ["path"],
    }
    required_permissions = [(ResourceType.FILESYSTEM, PermissionLevel.READ)]

    def __init__(self, sandbox_manager: Any) -> None:
        self._sandbox = sandbox_manager

    def execute(self, **kwargs: Any) -> ToolResult:
        path = kwargs.get("path", "")
        if not path:
            return ToolResult(success=False, error="No path provided")
        try:
            content = self._sandbox.read_file(path)
            return ToolResult(success=True, output=content.decode("utf-8", errors="replace"))
        except Exception as exc:
            return ToolResult(success=False, error=str(exc))


class FileWriteTool(Tool):
    name = "file_write"
    description = "Write content to a file in the sandbox."
    parameters_schema = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "File path inside the sandbox"},
            "content": {"type": "string", "description": "Content to write"},
        },
        "required": ["path", "content"],
    }
    required_permissions = [(ResourceType.FILESYSTEM, PermissionLevel.WRITE)]

    def __init__(self, sandbox_manager: Any) -> None:
        self._sandbox = sandbox_manager

    def execute(self, **kwargs: Any) -> ToolResult:
        path = kwargs.get("path", "")
        content = kwargs.get("content", "")
        if not path:
            return ToolResult(success=False, error="No path provided")
        try:
            self._sandbox.write_file(path, content.encode("utf-8"))
            return ToolResult(success=True, output=f"Wrote {len(content)} bytes to {path}")
        except Exception as exc:
            return ToolResult(success=False, error=str(exc))


class PermissionCheckTool(Tool):
    name = "check_permission"
    description = "Check whether a specific permission is granted."
    parameters_schema = {
        "type": "object",
        "properties": {
            "resource": {"type": "string", "enum": ["filesystem", "network", "process", "system"]},
            "level": {"type": "string", "enum": ["read", "write", "execute", "admin"]},
            "path": {"type": "string", "description": "Optional path to check"},
        },
        "required": ["resource", "level"],
    }
    required_permissions = []  # meta-tool, always allowed

    def __init__(self, permission_manager: Any) -> None:
        self._pm = permission_manager

    def execute(self, **kwargs: Any) -> ToolResult:
        try:
            resource = ResourceType(kwargs["resource"])
            level = PermissionLevel(kwargs["level"])
            path = kwargs.get("path")
            allowed = self._pm.check_permission(resource, level, path)
            return ToolResult(
                success=True,
                output=f"{resource.value}:{level.value} → {'ALLOWED' if allowed else 'DENIED'}",
                data={"allowed": allowed},
            )
        except Exception as exc:
            return ToolResult(success=False, error=str(exc))
