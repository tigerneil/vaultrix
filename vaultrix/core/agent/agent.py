"""Vaultrix agent - the secure autonomous AI agent."""

import logging
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone

from vaultrix.core.sandbox import SandboxManager, SandboxConfig
from vaultrix.core.permissions import PermissionManager, PermissionDeniedException, PermissionSet, ResourceType, PermissionLevel
from vaultrix.core.hitl import HITLManager, ApprovalRequest, ApprovalStatus


logger = logging.getLogger(__name__)


class VaultrixAgent:
    """
    Vaultrix Agent - A secure, sandboxed autonomous AI agent.

    This agent operates within a strict security model:
    - All operations run in an isolated sandbox
    - Permissions are explicitly granted and checked
    - High-risk actions require human approval
    - All actions are logged and auditable
    """

    def __init__(
        self,
        sandbox_config: Optional[SandboxConfig] = None,
        permission_set: Optional[PermissionSet] = None,
        agent_id: Optional[str] = None,
        hitl_manager: Optional[HITLManager] = None,
    ):
        """
        Initialize a Vaultrix agent.

        Args:
            sandbox_config: Configuration for the sandbox environment
            permission_set: Permission set for the agent
            agent_id: Optional unique identifier for this agent
            hitl_manager: Optional HITLManager for human-in-the-loop approval
        """
        self.agent_id = agent_id or f"agent-{datetime.now(timezone.utc).timestamp()}"
        self.sandbox_manager = SandboxManager(config=sandbox_config)
        self.permission_manager = PermissionManager(permission_set=permission_set)
        self.hitl_manager = hitl_manager or HITLManager()

        self.session_start = datetime.now(timezone.utc)
        self.action_history: List[Dict[str, Any]] = []

        logger.info(f"Vaultrix agent initialized: {self.agent_id}")

    def start(self) -> None:
        """Start the agent and initialize the sandbox."""
        logger.info(f"Starting agent {self.agent_id}")
        self.sandbox_manager.create_sandbox()
        logger.info("Agent ready for operations")

    def stop(self) -> None:
        """Stop the agent and clean up resources."""
        logger.info(f"Stopping agent {self.agent_id}")
        self.sandbox_manager.destroy_sandbox()
        logger.info("Agent stopped")

    def execute_command(
        self,
        command: str,
        require_approval: bool = False,
    ) -> Dict[str, Any]:
        """
        Execute a command in the sandbox with permission checking.

        Args:
            command: Command to execute
            require_approval: Whether to require human approval

        Returns:
            Execution result with output and status

        Raises:
            PermissionDeniedException: If permissions are insufficient
        """
        # Check process execution permission
        self.permission_manager.require_permission(
            ResourceType.PROCESS,
            PermissionLevel.EXECUTE,
            metadata={"command": command}
        )

        # Check if approval is required
        needs_approval = require_approval or self.permission_manager.requires_approval(
            ResourceType.PROCESS,
            PermissionLevel.EXECUTE
        )

        if needs_approval:
            logger.warning(f"Command requires approval: {command}")
            risk_level = self.permission_manager.get_risk_level(ResourceType.PROCESS).value.upper()
            approval_request = ApprovalRequest(
                agent_id=self.agent_id,
                action_type="execute_command",
                resource_type=ResourceType.PROCESS.value,
                permission_level=PermissionLevel.EXECUTE.value,
                description=f"Execute command: {command}",
                risk_level=risk_level,
                metadata={"command": command},
            )
            status = self.hitl_manager.request_approval(approval_request)
            if status == ApprovalStatus.TIMEOUT:
                raise PermissionDeniedException(
                    f"Approval timed out for command: {command}"
                )
            if status == ApprovalStatus.DENIED:
                raise PermissionDeniedException(
                    f"Human approval denied for command: {command}"
                )

        # Execute in sandbox
        result = self.sandbox_manager.execute_command(command)

        # Log action
        self._log_action(
            action_type="execute_command",
            details={"command": command, "result": result},
        )

        return result

    def read_file(self, path: str) -> bytes:
        """
        Read a file from the sandbox.

        Args:
            path: Path to the file

        Returns:
            File contents

        Raises:
            PermissionDeniedException: If read permission is denied
        """
        self.permission_manager.require_permission(
            ResourceType.FILESYSTEM,
            PermissionLevel.READ,
            path=path,
        )

        content = self.sandbox_manager.read_file(path)

        self._log_action(
            action_type="read_file",
            details={"path": path, "size": len(content)},
        )

        return content

    def write_file(self, path: str, content: bytes) -> None:
        """
        Write a file to the sandbox.

        Args:
            path: Path to the file
            content: File contents

        Raises:
            PermissionDeniedException: If write permission is denied
        """
        self.permission_manager.require_permission(
            ResourceType.FILESYSTEM,
            PermissionLevel.WRITE,
            path=path,
            metadata={"size": len(content)},
        )

        # Check if approval needed for write operations
        if self.permission_manager.requires_approval(
            ResourceType.FILESYSTEM,
            PermissionLevel.WRITE
        ):
            logger.info(f"File write requires approval: {path}")
            risk_level = self.permission_manager.get_risk_level(ResourceType.FILESYSTEM).value.upper()
            approval_request = ApprovalRequest(
                agent_id=self.agent_id,
                action_type="write_file",
                resource_type=ResourceType.FILESYSTEM.value,
                permission_level=PermissionLevel.WRITE.value,
                description=f"Write file: {path} ({len(content)} bytes)",
                risk_level=risk_level,
                metadata={"path": path, "size": len(content)},
            )
            status = self.hitl_manager.request_approval(approval_request)
            if status == ApprovalStatus.TIMEOUT:
                raise PermissionDeniedException(
                    f"Approval timed out for file write: {path}"
                )
            if status == ApprovalStatus.DENIED:
                raise PermissionDeniedException(
                    f"Human approval denied for file write: {path}"
                )

        self.sandbox_manager.write_file(path, content)

        self._log_action(
            action_type="write_file",
            details={"path": path, "size": len(content)},
        )

    def get_status(self) -> Dict[str, Any]:
        """
        Get the current status of the agent.

        Returns:
            Dictionary with agent status information
        """
        sandbox_info = self.sandbox_manager.get_info()
        permission_summary = self.permission_manager.get_summary()

        return {
            "agent_id": self.agent_id,
            "session_start": self.session_start.isoformat(),
            "uptime_seconds": (datetime.now(timezone.utc) - self.session_start).total_seconds(),
            "sandbox": {
                "id": sandbox_info.id,
                "status": sandbox_info.status.value,
                "resource_usage": sandbox_info.resource_usage,
            },
            "permissions": permission_summary,
            "actions_executed": len(self.action_history),
        }

    def get_logs(self) -> Dict[str, Any]:
        """
        Get logs from the agent and sandbox.

        Returns:
            Dictionary with various logs
        """
        return {
            "sandbox_logs": self.sandbox_manager.get_logs(),
            "action_history": self.action_history,
            "access_log": self.permission_manager.get_access_log(),
        }

    def _log_action(self, action_type: str, details: Dict[str, Any]) -> None:
        """Log an action to the action history."""
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "action_type": action_type,
            "details": details,
        }
        self.action_history.append(log_entry)

        # Keep history manageable
        if len(self.action_history) > 1000:
            self.action_history = self.action_history[-1000:]

    def __enter__(self):
        """Context manager entry."""
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.stop()
