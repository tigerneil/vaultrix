"""Local-process sandbox backend.

Runs commands in isolated subprocess with resource limits.
Works on any machine — no Docker required.  Provides weaker isolation
than Docker but is suitable for development and demos.
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from vaultrix.core.sandbox.backend import SandboxBackend
from vaultrix.core.sandbox.models import (
    SandboxConfig,
    SandboxInfo,
    SandboxStatus,
)

logger = logging.getLogger(__name__)


class LocalBackend(SandboxBackend):
    """Subprocess-based sandbox with filesystem isolation.

    Creates a temporary workspace directory and restricts all file
    operations to that directory.  Commands run as the current user
    with ``subprocess.run`` and a configurable timeout.
    """

    def __init__(self) -> None:
        self._status = SandboxStatus.STOPPED
        self._id: Optional[str] = None
        self._workspace: Optional[Path] = None
        self._config: Optional[SandboxConfig] = None
        self._logs: List[str] = []
        self._created_at: Optional[str] = None

    # -- SandboxBackend interface --------------------------------------------

    def create(self, config: SandboxConfig) -> str:
        if self._workspace is not None:
            self.destroy()

        self._config = config
        self._status = SandboxStatus.CREATING
        self._id = uuid.uuid4().hex[:12]

        # Create isolated temp workspace
        self._workspace = Path(tempfile.mkdtemp(prefix="vaultrix_"))
        (self._workspace / "workspace").mkdir(exist_ok=True)

        self._created_at = self._now_iso()
        self._status = SandboxStatus.RUNNING
        self._log(f"Local sandbox created: {self._id} at {self._workspace}")
        return self._id

    def destroy(self) -> None:
        if self._workspace and self._workspace.exists():
            shutil.rmtree(self._workspace, ignore_errors=True)
            self._log(f"Local sandbox {self._id} destroyed")
        self._workspace = None
        self._status = SandboxStatus.STOPPED

    def execute(
        self,
        command: List[str],
        *,
        timeout: Optional[int] = None,
        workdir: Optional[str] = None,
    ) -> Dict[str, Any]:
        self._require_running()
        assert self._workspace is not None

        effective_timeout = timeout or (self._config.execution_timeout if self._config else 300)
        cwd = str(self._workspace / "workspace")
        if workdir:
            resolved = (self._workspace / workdir.lstrip("/")).resolve()
            if str(resolved).startswith(str(self._workspace)):
                cwd = str(resolved)

        env = {**os.environ, "VAULTRIX_SANDBOX": "local", "HOME": str(self._workspace)}

        try:
            proc = subprocess.run(
                command,
                capture_output=True,
                timeout=effective_timeout,
                cwd=cwd,
                env=env,
            )
            stdout = proc.stdout.decode("utf-8", errors="replace")
            stderr = proc.stderr.decode("utf-8", errors="replace")
            self._log(f"exec {command!r} → exit {proc.returncode}")
            return {
                "exit_code": proc.returncode,
                "stdout": stdout,
                "stderr": stderr,
                "timestamp": self._now_iso(),
            }
        except subprocess.TimeoutExpired:
            self._log(f"exec {command!r} → TIMEOUT")
            return {
                "exit_code": -1,
                "stdout": "",
                "stderr": f"Command timed out after {effective_timeout}s",
                "timestamp": self._now_iso(),
            }
        except Exception as exc:
            from vaultrix.core.sandbox.manager import SandboxException
            raise SandboxException(f"Failed to execute command: {exc}")

    def read_file(self, path: str) -> bytes:
        self._require_running()
        real = self._resolve_path(path)
        return real.read_bytes()

    def write_file(self, path: str, content: bytes) -> None:
        self._require_running()
        real = self._resolve_path(path)
        real.parent.mkdir(parents=True, exist_ok=True)
        real.write_bytes(content)

    def pause(self) -> None:
        self._require_running()
        self._status = SandboxStatus.PAUSED

    def resume(self) -> None:
        if self._status != SandboxStatus.PAUSED:
            from vaultrix.core.sandbox.manager import SandboxException
            raise SandboxException("Sandbox is not paused")
        self._status = SandboxStatus.RUNNING

    def get_info(self) -> SandboxInfo:
        return SandboxInfo(
            id=self._id or "none",
            name=self._config.name if self._config and self._config.name else f"local-{self._id or 'none'}",
            status=self._status,
            created_at=self._created_at or self._now_iso(),
            config=self._config or SandboxConfig(),
            resource_usage={
                "backend": "local",
                "workspace": str(self._workspace),
            },
        )

    def get_logs(self, tail: int = 100) -> List[str]:
        return self._logs[-tail:]

    @property
    def status(self) -> SandboxStatus:
        return self._status

    @property
    def sandbox_id(self) -> Optional[str]:
        return self._id

    # -- internal helpers ----------------------------------------------------

    def _require_running(self) -> None:
        if self._workspace is None or self._status != SandboxStatus.RUNNING:
            from vaultrix.core.sandbox.manager import SandboxException
            raise SandboxException("Sandbox is not running")

    def _resolve_path(self, path: str) -> Path:
        """Map a sandbox-internal path to a real filesystem path, safely."""
        assert self._workspace is not None
        clean = Path(path.lstrip("/"))
        real = (self._workspace / clean).resolve()
        if not str(real).startswith(str(self._workspace.resolve())):
            from vaultrix.core.sandbox.manager import SandboxException
            raise SandboxException(f"Path escapes sandbox: {path}")
        return real

    def _log(self, msg: str) -> None:
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        line = f"[{ts}] {msg}"
        self._logs.append(line)
        logger.debug(line)
        if len(self._logs) > 2000:
            self._logs = self._logs[-1000:]
