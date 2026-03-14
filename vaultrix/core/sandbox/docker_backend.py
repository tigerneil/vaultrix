"""Docker-based sandbox backend.

Requires the ``docker`` Python package and a running Docker daemon.
Import is intentionally lazy so the rest of vaultrix works without Docker.
"""

from __future__ import annotations

import io
import logging
import tarfile
from typing import Any, Dict, List, Optional

from vaultrix.core.sandbox.backend import SandboxBackend
from vaultrix.core.sandbox.models import (
    SandboxConfig,
    SandboxInfo,
    SandboxStatus,
)

logger = logging.getLogger(__name__)


def _docker_client():
    """Lazy-import docker and return a client.  Raises SandboxException on failure."""
    from vaultrix.core.sandbox.manager import SandboxException

    try:
        import docker
        from docker.errors import DockerException
    except ImportError:
        raise SandboxException(
            "Docker SDK not available. Install with: pip install docker"
        )
    try:
        client = docker.from_env()
        client.ping()
        return client
    except DockerException as exc:
        raise SandboxException(f"Failed to connect to Docker: {exc}")


class DockerBackend(SandboxBackend):
    """Runs commands inside a Docker container."""

    def __init__(self) -> None:
        self._client: Any = None
        self._container: Any = None
        self._status = SandboxStatus.STOPPED
        self._config: Optional[SandboxConfig] = None

    # -- SandboxBackend interface --------------------------------------------

    def create(self, config: SandboxConfig) -> str:
        import docker  # lazy
        from docker.errors import DockerException, NotFound, APIError

        if self._container is not None:
            self.destroy()

        self._client = _docker_client()
        self._config = config
        self._status = SandboxStatus.CREATING

        try:
            try:
                self._client.images.get(config.image)
            except NotFound:
                logger.info("Image %s not found, pulling python:3.11-slim…", config.image)
                config = config.model_copy(update={"image": "python:3.11-slim"})
                self._config = config
                self._client.images.pull(config.image)

            docker_config = config.to_docker_config()
            self._container = self._client.containers.create(**docker_config)
            self._container.start()
            self._status = SandboxStatus.RUNNING
            cid = self._container.id[:12]
            logger.info("Docker sandbox created: %s", cid)
            return cid
        except (DockerException, APIError) as exc:
            self._status = SandboxStatus.ERROR
            from vaultrix.core.sandbox.manager import SandboxException
            raise SandboxException(f"Failed to create sandbox: {exc}")

    def destroy(self) -> None:
        if self._container is None:
            return
        try:
            self._container.stop(timeout=5)
            self._container.remove(force=True)
            logger.info("Docker sandbox destroyed")
        except Exception as exc:
            logger.error("Error destroying sandbox: %s", exc)
        finally:
            self._container = None
            self._status = SandboxStatus.STOPPED

    def execute(
        self,
        command: List[str],
        *,
        timeout: Optional[int] = None,
        workdir: Optional[str] = None,
    ) -> Dict[str, Any]:
        self._require_running()
        exec_kw: Dict[str, Any] = {
            "cmd": command,
            "stdout": True,
            "stderr": True,
        }
        if workdir:
            exec_kw["workdir"] = workdir

        result = self._container.exec_run(**exec_kw)
        return {
            "exit_code": result.exit_code,
            "stdout": result.output.decode("utf-8", errors="replace"),
            "stderr": "",
            "timestamp": self._now_iso(),
        }

    def read_file(self, path: str) -> bytes:
        self._require_running()
        bits, _ = self._container.get_archive(path)
        buf = io.BytesIO()
        for chunk in bits:
            buf.write(chunk)
        buf.seek(0)
        tar = tarfile.open(fileobj=buf)
        member = tar.getmembers()[0]
        return tar.extractfile(member).read()  # type: ignore[union-attr]

    def write_file(self, path: str, content: bytes) -> None:
        self._require_running()
        tar_stream = io.BytesIO()
        with tarfile.open(fileobj=tar_stream, mode="w") as tar:
            info = tarfile.TarInfo(name=path.split("/")[-1])
            info.size = len(content)
            tar.addfile(info, io.BytesIO(content))
        tar_stream.seek(0)
        directory = "/".join(path.split("/")[:-1]) or "/"
        self._container.put_archive(directory, tar_stream)

    def pause(self) -> None:
        self._require_running()
        self._container.pause()
        self._status = SandboxStatus.PAUSED

    def resume(self) -> None:
        if self._container is None:
            from vaultrix.core.sandbox.manager import SandboxException
            raise SandboxException("No sandbox to resume")
        self._container.unpause()
        self._status = SandboxStatus.RUNNING

    def get_info(self) -> SandboxInfo:
        self._require_running()
        self._container.reload()
        stats = self._container.stats(stream=False)
        return SandboxInfo(
            id=self._container.id[:12],
            name=self._container.name,
            status=self._status,
            created_at=self._container.attrs["Created"],
            config=self._config or SandboxConfig(),
            resource_usage={
                "cpu_usage": stats.get("cpu_stats", {}),
                "memory_usage": stats.get("memory_stats", {}),
            },
        )

    def get_logs(self, tail: int = 100) -> List[str]:
        if self._container is None:
            return []
        try:
            raw = self._container.logs(tail=tail).decode("utf-8", errors="replace")
            return raw.split("\n")
        except Exception:
            return []

    @property
    def status(self) -> SandboxStatus:
        return self._status

    @property
    def sandbox_id(self) -> Optional[str]:
        return self._container.id[:12] if self._container else None

    # -- internal helpers ----------------------------------------------------

    def _require_running(self) -> None:
        if self._container is None or self._status != SandboxStatus.RUNNING:
            from vaultrix.core.sandbox.manager import SandboxException
            raise SandboxException("Sandbox is not running")
