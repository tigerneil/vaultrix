"""Permission models and enumerations.

Security-hardened permission model supporting:
- Multiple permissions per resource type
- Path-traversal-safe path matching
- Rate limiting and temporal scoping
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
import posixpath
from typing import List, Optional

from pydantic import BaseModel, Field


# ── Enums ──────────────────────────────────────────────────────────────────

class PermissionLevel(str, Enum):
    NONE = "none"
    READ = "read"
    WRITE = "write"
    EXECUTE = "execute"
    ADMIN = "admin"


class ResourceType(str, Enum):
    FILESYSTEM = "filesystem"
    NETWORK = "network"
    PROCESS = "process"
    SYSTEM = "system"
    DATABASE = "database"
    ENVIRONMENT = "environment"


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


# ── Hierarchy helper ───────────────────────────────────────────────────────

_LEVEL_RANK = {
    PermissionLevel.NONE: 0,
    PermissionLevel.READ: 1,
    PermissionLevel.WRITE: 2,
    PermissionLevel.EXECUTE: 3,
    PermissionLevel.ADMIN: 4,
}


def _safe_path_match(requested: str, allowed: str) -> bool:
    """Check *requested* falls under *allowed*, immune to path traversal.

    Uses ``posixpath.normpath`` which collapses ``..`` segments, so
    ``/workspace/../etc`` becomes ``/etc`` before comparison.
    """
    norm = posixpath.normpath("/" + requested.lstrip("/"))
    allowed_norm = posixpath.normpath("/" + allowed.lstrip("/"))
    if norm == allowed_norm:
        return True
    return norm.startswith(allowed_norm.rstrip("/") + "/")


# ── Models ─────────────────────────────────────────────────────────────────

class Permission(BaseModel):
    """A single permission rule."""

    resource_type: ResourceType
    level: PermissionLevel
    paths: List[str] = Field(default_factory=list)
    whitelist: List[str] = Field(default_factory=list)
    max_size: Optional[int] = None
    enabled: bool = True
    risk_level: RiskLevel = RiskLevel.MEDIUM

    # Rate limiting
    max_requests_per_minute: Optional[int] = Field(
        None, description="Max allowed accesses per minute (None = unlimited)"
    )

    # Temporal scoping
    expires_at: Optional[datetime] = Field(
        None, description="UTC expiry time; None = never expires"
    )

    def is_expired(self) -> bool:
        if self.expires_at is None:
            return False
        return datetime.now(timezone.utc) >= self.expires_at


class PermissionSet(BaseModel):
    """A complete set of permissions for an agent session.

    Supports *multiple* ``Permission`` entries per ``ResourceType`` —
    access is granted if **any** matching rule allows it.
    """

    name: str = "default"
    description: Optional[str] = None
    permissions: List[Permission] = Field(default_factory=list)
    allow_skill_execution: bool = False

    # -- query helpers -------------------------------------------------------

    def get_permission(self, resource_type: ResourceType) -> Optional[Permission]:
        """Return the first matching permission (kept for back-compat)."""
        for perm in self.permissions:
            if perm.resource_type == resource_type:
                return perm
        return None

    def get_permissions(self, resource_type: ResourceType) -> List[Permission]:
        """Return *all* permissions for a resource type."""
        return [p for p in self.permissions if p.resource_type == resource_type]

    def check_access(
        self,
        resource_type: ResourceType,
        level: PermissionLevel,
        path: Optional[str] = None,
    ) -> bool:
        """Return ``True`` if any rule grants the requested access."""
        candidates = self.get_permissions(resource_type)
        if not candidates:
            return False

        for perm in candidates:
            if not perm.enabled or perm.is_expired():
                continue

            if _LEVEL_RANK.get(perm.level, 0) < _LEVEL_RANK.get(level, 0):
                continue

            # Path check (traversal-safe)
            if path and perm.paths:
                if not any(_safe_path_match(path, allowed) for allowed in perm.paths):
                    continue

            return True  # at least one rule matched

        return False


# ── Built-in permission presets ────────────────────────────────────────────

DEFAULT_SANDBOX_PERMISSIONS = PermissionSet(
    name="default_sandbox",
    description="Default secure sandbox permissions",
    permissions=[
        Permission(
            resource_type=ResourceType.FILESYSTEM,
            level=PermissionLevel.WRITE,
            paths=["/workspace"],
            risk_level=RiskLevel.MEDIUM,
        ),
        Permission(
            resource_type=ResourceType.NETWORK,
            level=PermissionLevel.NONE,
            enabled=False,
            risk_level=RiskLevel.HIGH,
        ),
        Permission(
            resource_type=ResourceType.PROCESS,
            level=PermissionLevel.EXECUTE,
            risk_level=RiskLevel.LOW,
        ),
        Permission(
            resource_type=ResourceType.SYSTEM,
            level=PermissionLevel.READ,
            risk_level=RiskLevel.LOW,
        ),
    ],
)

RESTRICTED_PERMISSIONS = PermissionSet(
    name="restricted",
    description="Highly restricted permissions for untrusted operations",
    permissions=[
        Permission(
            resource_type=ResourceType.FILESYSTEM,
            level=PermissionLevel.READ,
            paths=["/workspace/readonly"],
            risk_level=RiskLevel.LOW,
        ),
    ],
)

DEVELOPER_PERMISSIONS = PermissionSet(
    name="developer",
    description="Extended permissions for development and testing",
    permissions=[
        Permission(
            resource_type=ResourceType.FILESYSTEM,
            level=PermissionLevel.WRITE,
            paths=["/workspace"],
            risk_level=RiskLevel.MEDIUM,
        ),
        Permission(
            resource_type=ResourceType.NETWORK,
            level=PermissionLevel.EXECUTE,
            whitelist=["api.anthropic.com", "vaulthub.dev"],
            risk_level=RiskLevel.HIGH,
        ),
        Permission(
            resource_type=ResourceType.PROCESS,
            level=PermissionLevel.EXECUTE,
            risk_level=RiskLevel.MEDIUM,
        ),
    ],
    allow_skill_execution=True,
)
