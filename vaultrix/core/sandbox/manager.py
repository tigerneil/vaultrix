"""Sandbox manager — delegates to the best available backend.

Auto-selects Docker if available, otherwise falls back to the local
subprocess backend.  Never crashes on import.
"""

from __future__ import annotations

import logging
import shlex
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from vaultrix.core.sandbox.models import (
    SandboxConfig,
    SandboxInfo,
    SandboxStatus,
)

logger = logging.getLogger(__name__)


class SandboxException(Exception):
    """Base exception for sandbox operations."""


def _detect_backend():
    """Return the best available backend instance (Docker > Local)."""
    try:
        import docker  # noqa: F401
        client = docker.from_env()
        client.ping()
        from vaultrix.core.sandbox.docker_backend import DockerBackend
        return DockerBackend()
    except Exception:
        pass
    from vaultrix.core.sandbox.local_backend import LocalBackend
    return LocalBackend()


class SandboxManager:
    """Manages sandboxed execution via a pluggable backend.

    If *backend* is ``None`` the manager auto-detects Docker availability
    and falls back to a local-process sandbox.
    """

    def __init__(
        self,
        config: Optional[SandboxConfig] = None,
        backend: Optional["SandboxBackend"] = None,  # noqa: F821
    ):
        from vaultrix.core.sandbox.backend import SandboxBackend  # noqa: F811

        self.config = config or SandboxConfig()
        self._backend: SandboxBackend = backend or _detect_backend()
        logger.info(
            "SandboxManager using %s backend",
            type(self._backend).__name__,
        )

    # -- public API (backwards-compatible) -----------------------------------

    @property
    def status(self) -> SandboxStatus:
        return self._backend.status

    def create_sandbox(self, config: Optional[SandboxConfig] = None) -> str:
        return self._backend.create(config or self.config)

    def destroy_sandbox(self) -> None:
        self._backend.destroy()

    def execute_command(
        self,
        command: str,
        timeout: Optional[int] = None,
        workdir: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Execute *command* safely.

        The command string is split with ``shlex.split`` into an argv list
        so no shell meta-characters are interpreted.
        """
        argv = shlex.split(command)
        return self._backend.execute(argv, timeout=timeout, workdir=workdir)

    def read_file(self, path: str) -> bytes:
        return self._backend.read_file(path)

    def write_file(self, path: str, content: bytes) -> None:
        self._backend.write_file(path, content)

    def pause_sandbox(self) -> None:
        self._backend.pause()

    def resume_sandbox(self) -> None:
        self._backend.resume()

    def get_info(self) -> SandboxInfo:
        return self._backend.get_info()

    def get_logs(self, tail: int = 100) -> List[str]:
        return self._backend.get_logs(tail)

    def __enter__(self):
        self.create_sandbox()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.destroy_sandbox()
