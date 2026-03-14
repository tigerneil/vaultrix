"""Permission manager for controlling agent access.

Includes rate limiting enforcement and temporal expiry checking.
"""

from __future__ import annotations

import collections
import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from vaultrix.core.permissions.models import (
    Permission,
    PermissionSet,
    ResourceType,
    PermissionLevel,
    RiskLevel,
    DEFAULT_SANDBOX_PERMISSIONS,
)

logger = logging.getLogger(__name__)


class PermissionDeniedException(Exception):
    """Raised when an operation is denied by permissions."""


class PermissionManager:
    """Manages permissions and access control for agent operations."""

    def __init__(self, permission_set: Optional[PermissionSet] = None):
        self.permission_set = permission_set or DEFAULT_SANDBOX_PERMISSIONS
        self.access_log: List[Dict[str, Any]] = []
        # Rate-limit tracking: key=(resource, level) → deque of timestamps
        self._rate_log: Dict[tuple, collections.deque] = {}
        logger.info("Permission manager initialized with set: %s", self.permission_set.name)

    # -- public API ----------------------------------------------------------

    def check_permission(
        self,
        resource_type: ResourceType,
        level: PermissionLevel,
        path: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        allowed = self.permission_set.check_access(resource_type, level, path)

        # Rate-limit check (only if structurally allowed)
        if allowed:
            allowed = self._check_rate_limit(resource_type, level)

        self._log_access(
            resource_type=resource_type,
            level=level,
            path=path,
            allowed=allowed,
            metadata=metadata,
        )
        if not allowed:
            logger.warning(
                "Permission denied: %s %s %s",
                resource_type.value,
                level.value,
                f"for path {path}" if path else "",
            )
        return allowed

    def require_permission(
        self,
        resource_type: ResourceType,
        level: PermissionLevel,
        path: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        if not self.check_permission(resource_type, level, path, metadata):
            raise PermissionDeniedException(
                f"Access denied for {resource_type.value} with level {level.value}"
                f"{f' at path {path}' if path else ''}"
            )

    def get_risk_level(self, resource_type: ResourceType) -> RiskLevel:
        perm = self.permission_set.get_permission(resource_type)
        return perm.risk_level if perm else RiskLevel.CRITICAL

    def requires_approval(self, resource_type: ResourceType, level: PermissionLevel) -> bool:
        risk_level = self.get_risk_level(resource_type)
        if risk_level in (RiskLevel.HIGH, RiskLevel.CRITICAL):
            return True
        if risk_level == RiskLevel.MEDIUM and level in (
            PermissionLevel.WRITE,
            PermissionLevel.EXECUTE,
            PermissionLevel.ADMIN,
        ):
            return True
        return False

    def update_permission_set(self, permission_set: PermissionSet) -> None:
        logger.info("Updating permission set to: %s", permission_set.name)
        self.permission_set = permission_set
        self._rate_log.clear()

    def get_access_log(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        if limit:
            return self.access_log[-limit:]
        return self.access_log

    def export_permissions(self) -> Dict[str, Any]:
        return self.permission_set.model_dump()

    def get_summary(self) -> Dict[str, Any]:
        total_attempts = len(self.access_log)
        denied_attempts = sum(1 for entry in self.access_log if not entry["allowed"])
        return {
            "permission_set": self.permission_set.name,
            "description": self.permission_set.description,
            "total_access_attempts": total_attempts,
            "denied_attempts": denied_attempts,
            "approval_required_resources": [
                perm.resource_type.value
                if hasattr(perm.resource_type, "value")
                else perm.resource_type
                for perm in self.permission_set.permissions
                if perm.risk_level in (RiskLevel.HIGH, RiskLevel.CRITICAL)
            ],
        }

    # -- rate limiting -------------------------------------------------------

    def _check_rate_limit(self, resource_type: ResourceType, level: PermissionLevel) -> bool:
        """Return False if any matching permission's rate limit is exceeded."""
        perms = self.permission_set.get_permissions(resource_type)
        now = time.monotonic()
        for perm in perms:
            cap = perm.max_requests_per_minute
            if cap is None:
                continue
            key = (resource_type, level)
            bucket = self._rate_log.setdefault(key, collections.deque())
            # Purge entries older than 60 s
            while bucket and bucket[0] < now - 60:
                bucket.popleft()
            if len(bucket) >= cap:
                return False
            bucket.append(now)
        return True

    # -- internal logging ----------------------------------------------------

    def _log_access(
        self,
        resource_type: ResourceType,
        level: PermissionLevel,
        path: Optional[str],
        allowed: bool,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "resource_type": resource_type.value,
            "level": level.value,
            "path": path,
            "allowed": allowed,
            "permission_set": self.permission_set.name,
            "metadata": metadata or {},
        }
        self.access_log.append(entry)
        if len(self.access_log) > 1000:
            self.access_log = self.access_log[-1000:]
