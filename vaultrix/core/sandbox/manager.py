"""Sandbox manager — delegates to the best available backend.

Auto-selects Docker if available, then macOS sandbox-exec, and finally
falls back to the local subprocess backend.  Never crashes on import.
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
    """Return the best available backend instance (Docker > macOS > Local)."""
    # Try Docker first
    try:
        import docker  # noqa: F401
        client = docker.from_env()
        client.ping()
        from vaultrix.core.sandbox.docker_backend import DockerBackend
        return DockerBackend()
    except Exception:
        pass
    # Try macOS sandbox-exec
    try:
        from vaultrix.core.sandbox.macos_backend import MacOSBackend, _sandbox_exec_available
        if _sandbox_exec_available():
            return MacOSBackend()
    except Exception:
        pass
    # Fallback to local subprocess
    from vaultrix.core.sandbox.local_backend import LocalBackend
    return LocalBackend()


def _backend_by_name(name: str):
    """Return a backend instance for the given name."""
    if name == "docker":
        from vaultrix.core.sandbox.docker_backend import DockerBackend
        return DockerBackend()
    if name == "macos":
        from vaultrix.core.sandbox.macos_backend import MacOSBackend
        return MacOSBackend()
    if name == "local":
        from vaultrix.core.sandbox.local_backend import LocalBackend
        return LocalBackend()
    raise SandboxException(f"Unknown sandbox backend: {name!r}")


class SandboxManager:
    """Manages sandboxed execution via a pluggable backend.

    If *backend* is ``None`` the manager auto-detects the best available
    backend (Docker > macOS sandbox-exec > local subprocess).
    Pass *backend_name* (``"docker"``, ``"macos"``, ``"local"``) to force
    a specific backend.
    """

    def __init__(
        self,
        config: Optional[SandboxConfig] = None,
        backend: Optional["SandboxBackend"] = None,  # noqa: F821
        backend_name: Optional[str] = None,
    ):
        from vaultrix.core.sandbox.backend import SandboxBackend  # noqa: F811

        self.config = config or SandboxConfig()
        if backend is not None:
            self._backend: SandboxBackend = backend
        elif backend_name and backend_name != "auto":
            self._backend = _backend_by_name(backend_name)
        else:
            self._backend = _detect_backend()
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
