"""Security-focused tests for Vaultrix.

Covers:
- Path traversal prevention
- Rate limiting
- Permission expiry
- Multi-permission matching
- AST scanner detection
"""

import time
import tempfile
from datetime import datetime, timezone, timedelta
from pathlib import Path

import pytest

from vaultrix.core.permissions import (
    PermissionManager,
    PermissionSet,
    Permission,
    ResourceType,
    PermissionLevel,
    RiskLevel,
)
from vaultrix.core.permissions.models import _safe_path_match
from vaultrix.safehub.scanner.analyzer import scan_skill, Severity


# ── Path traversal tests ───────────────────────────────────────────────────


class TestPathTraversal:
    def test_direct_traversal_blocked(self):
        """``/workspace/../etc/passwd`` must NOT match ``/workspace``."""
        assert not _safe_path_match("/workspace/../etc/passwd", "/workspace")

    def test_double_dot_in_middle(self):
        assert not _safe_path_match("/workspace/foo/../../etc/shadow", "/workspace")

    def test_valid_subpath_allowed(self):
        assert _safe_path_match("/workspace/data/file.txt", "/workspace")

    def test_exact_match_allowed(self):
        assert _safe_path_match("/workspace", "/workspace")

    def test_partial_name_not_matched(self):
        """``/workspace_evil`` should not match ``/workspace``."""
        assert not _safe_path_match("/workspace_evil/file", "/workspace")

    def test_permission_set_blocks_traversal(self):
        perm_set = PermissionSet(
            name="test",
            permissions=[
                Permission(
                    resource_type=ResourceType.FILESYSTEM,
                    level=PermissionLevel.READ,
                    paths=["/workspace"],
                )
            ],
        )
        assert not perm_set.check_access(
            ResourceType.FILESYSTEM,
            PermissionLevel.READ,
            "/workspace/../etc/passwd",
        )


# ── Rate limiting tests ───────────────────────────────────────────────────


class TestRateLimiting:
    def test_rate_limit_enforced(self):
        perm_set = PermissionSet(
            name="rate_test",
            permissions=[
                Permission(
                    resource_type=ResourceType.FILESYSTEM,
                    level=PermissionLevel.READ,
                    max_requests_per_minute=3,
                )
            ],
        )
        pm = PermissionManager(perm_set)
        assert pm.check_permission(ResourceType.FILESYSTEM, PermissionLevel.READ)
        assert pm.check_permission(ResourceType.FILESYSTEM, PermissionLevel.READ)
        assert pm.check_permission(ResourceType.FILESYSTEM, PermissionLevel.READ)
        # 4th should be denied
        assert not pm.check_permission(ResourceType.FILESYSTEM, PermissionLevel.READ)

    def test_no_rate_limit_allows_many(self):
        perm_set = PermissionSet(
            name="unlimited",
            permissions=[
                Permission(
                    resource_type=ResourceType.SYSTEM,
                    level=PermissionLevel.READ,
                    # max_requests_per_minute defaults to None
                )
            ],
        )
        pm = PermissionManager(perm_set)
        for _ in range(50):
            assert pm.check_permission(ResourceType.SYSTEM, PermissionLevel.READ)


# ── Temporal expiry tests ─────────────────────────────────────────────────


class TestExpiry:
    def test_expired_permission_denied(self):
        perm_set = PermissionSet(
            name="expiry_test",
            permissions=[
                Permission(
                    resource_type=ResourceType.FILESYSTEM,
                    level=PermissionLevel.READ,
                    expires_at=datetime.now(timezone.utc) - timedelta(seconds=1),
                )
            ],
        )
        pm = PermissionManager(perm_set)
        assert not pm.check_permission(ResourceType.FILESYSTEM, PermissionLevel.READ)

    def test_future_expiry_allowed(self):
        perm_set = PermissionSet(
            name="future_test",
            permissions=[
                Permission(
                    resource_type=ResourceType.FILESYSTEM,
                    level=PermissionLevel.READ,
                    expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
                )
            ],
        )
        pm = PermissionManager(perm_set)
        assert pm.check_permission(ResourceType.FILESYSTEM, PermissionLevel.READ)


# ── Multi-permission tests ────────────────────────────────────────────────


class TestMultiPermission:
    def test_multiple_perms_same_resource(self):
        """Two filesystem permissions — one for /data, one for /output."""
        perm_set = PermissionSet(
            name="multi",
            permissions=[
                Permission(
                    resource_type=ResourceType.FILESYSTEM,
                    level=PermissionLevel.READ,
                    paths=["/workspace/data"],
                ),
                Permission(
                    resource_type=ResourceType.FILESYSTEM,
                    level=PermissionLevel.WRITE,
                    paths=["/workspace/output"],
                ),
            ],
        )
        # Read from /data — allowed by first rule
        assert perm_set.check_access(
            ResourceType.FILESYSTEM, PermissionLevel.READ, "/workspace/data/f.txt"
        )
        # Write to /output — allowed by second rule
        assert perm_set.check_access(
            ResourceType.FILESYSTEM, PermissionLevel.WRITE, "/workspace/output/f.txt"
        )
        # Write to /data — denied (first rule is READ only)
        assert not perm_set.check_access(
            ResourceType.FILESYSTEM, PermissionLevel.WRITE, "/workspace/data/f.txt"
        )


# ── AST scanner tests ────────────────────────────────────────────────────


class TestScanner:
    def test_detects_eval(self, tmp_path: Path):
        (tmp_path / "bad.py").write_text("result = eval('1+1')\n")
        result = scan_skill(tmp_path, "bad_skill")
        assert not result.passed
        assert any("eval" in f.message for f in result.findings)

    def test_detects_subprocess(self, tmp_path: Path):
        (tmp_path / "bad.py").write_text("import subprocess\n")
        result = scan_skill(tmp_path, "sub_skill")
        assert not result.passed

    def test_clean_skill_passes(self, tmp_path: Path):
        (tmp_path / "clean.py").write_text("x = 1 + 2\nprint(x)\n")
        result = scan_skill(tmp_path, "clean_skill")
        assert result.passed

    def test_detects_os_system(self, tmp_path: Path):
        (tmp_path / "bad.py").write_text("import os\nos.system('ls')\n")
        result = scan_skill(tmp_path, "os_skill")
        assert not result.passed
        assert any("os" in f.message.lower() for f in result.findings)
