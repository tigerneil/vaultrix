"""Sandbox manager — delegates to the best available backend.

Auto-selects Docker if available, otherwise falls back to the local
macOS sandbox-exec backend when available, then the local subprocess
backend.  Never crashes on import.
"""

from __future__ import annotations

import logging
import os
import shlex
from typing import Any, Dict, List, Optional

from vaultrix.core.sandbox.models import (
    SandboxConfig,
    SandboxInfo,
    SandboxStatus,
)

logger = logging.getLogger(__name__)


class SandboxException(Exception):
    """Base exception for sandbox operations."""

def _docker_backend():
    """Return the best available backend instance (Docker > Local)."""
    try:
        import docker  # noqa: F401
        client = docker.from_env()
        client.ping()
        from vaultrix.core.sandbox.docker_backend import DockerBackend
        return DockerBackend()
    except Exception:
        return None


def _macos_backend():
    try:
        from vaultrix.core.sandbox.macos_backend import MacOSBackend, _sandbox_exec_available

        if _sandbox_exec_available():
            return MacOSBackend()
    except Exception:
        return None
    return None


def _local_backend():
    from vaultrix.core.sandbox.local_backend import LocalBackend
    return LocalBackend()

def _detect_backend(preferred: str = "auto"):
    """Return the requested backend or the strongest available backend."""
    if preferred == "docker":
        backend = _docker_backend()
        if backend is None:
            raise SandboxException("Docker backend requested but Docker is unavailable")
        return backend
    if preferred == "macos":
        backend = _macos_backend()
        if backend is None:
            raise SandboxException("macOS backend requested but sandbox-exec is unavailable")
        return backend
    if preferred == "local":
        return _local_backend()
    if preferred != "auto":
        raise SandboxException(f"Unknown sandbox backend: {preferred}")

    return _docker_backend() or _macos_backend() or _local_backend()


class SandboxManager:
    """Manages sandboxed execution via a pluggable backend.

    If *backend* is ``None`` the manager auto-detects Docker availability
    and falls back to a local-process sandbox.
    """

    def __init__(
        self,
        config: Optional[SandboxConfig] = None,
        backend: Optional["SandboxBackend"] = None,  # noqa: F821
        backend_name: Optional[str] = None,
    ):
        from vaultrix.core.sandbox.backend import SandboxBackend  # noqa: F811

        self.config = config or SandboxConfig()
        preferred_backend = backend_name or os.environ.get("VAULTRIX_SANDBOX_BACKEND", "auto")
        self._backend: SandboxBackend = backend or _detect_backend(preferred_backend)
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
