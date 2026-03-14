"""Sandbox configuration and status models."""

from enum import Enum
from typing import Optional, Dict, List
from pydantic import BaseModel, Field


class SandboxStatus(str, Enum):
    """Status of a sandbox instance."""

    CREATING = "creating"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPED = "stopped"
    ERROR = "error"


class ResourceLimits(BaseModel):
    """Resource limits for sandbox."""

    cpu_quota: Optional[float] = Field(1.0, description="CPU quota (1.0 = 1 core)")
    memory_limit: Optional[str] = Field("512m", description="Memory limit (e.g., '512m', '1g')")
    storage_limit: Optional[str] = Field("10g", description="Storage limit")
    network_bandwidth: Optional[str] = Field(None, description="Network bandwidth limit")
    max_processes: Optional[int] = Field(50, description="Maximum number of processes")


class NetworkConfig(BaseModel):
    """Network configuration for sandbox."""

    enabled: bool = Field(False, description="Enable network access")
    mode: str = Field("none", description="Network mode: none, bridge, host")
    whitelist_domains: List[str] = Field(default_factory=list, description="Allowed domains")
    whitelist_ips: List[str] = Field(default_factory=list, description="Allowed IP addresses")
    block_ports: List[int] = Field(
        default_factory=lambda: [22, 23, 3389],  # Block SSH, Telnet, RDP by default
        description="Ports to block"
    )


class FilesystemConfig(BaseModel):
    """Filesystem configuration for sandbox."""

    workspace_path: str = Field("/workspace", description="Main workspace path inside sandbox")
    readonly_paths: List[str] = Field(default_factory=list, description="Readonly mount paths")
    writable_paths: List[str] = Field(
        default_factory=lambda: ["/workspace"],
        description="Writable paths"
    )
    max_file_size: str = Field("100m", description="Maximum individual file size")
    blocked_extensions: List[str] = Field(
        default_factory=lambda: [".exe", ".dll", ".so", ".dylib"],
        description="Blocked file extensions"
    )


class SandboxConfig(BaseModel):
    """Complete sandbox configuration."""

    name: str = Field("vaultrix-sandbox", description="Sandbox name")
    image: str = Field("vaultrix/runtime:latest", description="Docker image to use")
    resource_limits: ResourceLimits = Field(default_factory=ResourceLimits)
    network: NetworkConfig = Field(default_factory=NetworkConfig)
    filesystem: FilesystemConfig = Field(default_factory=FilesystemConfig)

    # Security options
    privileged: bool = Field(False, description="Run in privileged mode (dangerous!)")
    read_only_rootfs: bool = Field(True, description="Make root filesystem read-only")
    no_new_privileges: bool = Field(True, description="Prevent privilege escalation")
    drop_capabilities: List[str] = Field(
        default_factory=lambda: [
            "CAP_SYS_ADMIN",
            "CAP_NET_ADMIN",
            "CAP_SYS_MODULE",
            "CAP_SYS_RAWIO",
        ],
        description="Linux capabilities to drop"
    )

    # Monitoring
    enable_logging: bool = Field(True, description="Enable comprehensive logging")
    log_commands: bool = Field(True, description="Log all executed commands")

    # Timeout
    execution_timeout: int = Field(300, description="Maximum execution time in seconds")
    idle_timeout: int = Field(1800, description="Idle timeout in seconds")

    def to_docker_config(self) -> Dict:
        """Convert to Docker SDK configuration."""
        config = {
            "image": self.image,
            "name": self.name,
            "detach": True,
            "stdin_open": True,
            "tty": True,
            "working_dir": self.filesystem.workspace_path,
            "security_opt": [],
        }

        # Resource limits
        if self.resource_limits:
            config["cpu_quota"] = int(self.resource_limits.cpu_quota * 100000)
            config["mem_limit"] = self.resource_limits.memory_limit
            config["pids_limit"] = self.resource_limits.max_processes

        # Network
        config["network_mode"] = self.network.mode

        # Security options
        if self.read_only_rootfs:
            config["read_only"] = True

        if self.no_new_privileges:
            config["security_opt"].append("no-new-privileges")

        if self.drop_capabilities:
            config["cap_drop"] = self.drop_capabilities

        return config


class SandboxInfo(BaseModel):
    """Information about a running sandbox."""

    id: str
    name: str
    status: SandboxStatus
    created_at: str
    config: SandboxConfig
    resource_usage: Optional[Dict] = None
    logs: Optional[List[str]] = None
