"""Abstract sandbox backend interface.

All sandbox implementations (Docker, local process, Firecracker, etc.)
must implement this protocol.
"""

from __future__ import annotations

import abc
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from vaultrix.core.sandbox.models import SandboxConfig, SandboxInfo, SandboxStatus


class SandboxBackend(abc.ABC):
    """Abstract base class for sandbox execution backends."""

    @abc.abstractmethod
    def create(self, config: SandboxConfig) -> str:
        """Create a new sandbox instance.

        Returns:
            Unique identifier for the sandbox.
        """

    @abc.abstractmethod
    def destroy(self) -> None:
        """Destroy the sandbox and release resources."""

    @abc.abstractmethod
    def execute(
        self,
        command: List[str],
        *,
        timeout: Optional[int] = None,
        workdir: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Execute a command in the sandbox.

        Args:
            command: Command as an argv list (no shell interpolation).
            timeout: Max execution seconds.
            workdir: Working directory inside the sandbox.

        Returns:
            Dict with keys: exit_code, stdout, stderr, timestamp.
        """

    @abc.abstractmethod
    def read_file(self, path: str) -> bytes:
        """Read a file from the sandbox."""

    @abc.abstractmethod
    def write_file(self, path: str, content: bytes) -> None:
        """Write a file into the sandbox."""

    @abc.abstractmethod
    def pause(self) -> None:
        """Pause execution."""

    @abc.abstractmethod
    def resume(self) -> None:
        """Resume execution."""

    @abc.abstractmethod
    def get_info(self) -> SandboxInfo:
        """Return runtime metadata about the sandbox."""

    @abc.abstractmethod
    def get_logs(self, tail: int = 100) -> List[str]:
        """Return recent log lines."""

    @property
    @abc.abstractmethod
    def status(self) -> SandboxStatus:
        """Current status."""

    @property
    @abc.abstractmethod
    def sandbox_id(self) -> Optional[str]:
        """Current sandbox identifier (None if not created)."""

    # -- convenience helpers (non-abstract) ----------------------------------

    @staticmethod
    def _now_iso() -> str:
        return datetime.now(timezone.utc).isoformat()
