"""Security-focused tests for Vaultrix.

Covers:
- Path traversal prevention
- Rate limiting
- Permission expiry
- Multi-permission matching
- AST scanner detection
- Config secret handling
- AgentLoop input validation
"""

from datetime import datetime, timezone, timedelta
from pathlib import Path
import pytest


from vaultrix.core.agent.loop import AgentLoop
from vaultrix.core.config import ConfigManager, VaultrixConfig
from vaultrix.core.permissions import (
    PermissionManager,
    PermissionSet,
    Permission,
    ResourceType,
    PermissionLevel,
)
from vaultrix.core.permissions.models import _safe_path_match
from vaultrix.core.tools.base import Tool, ToolRegistry, ToolResult
from vaultrix.safehub.scanner.analyzer import scan_skill


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


# ── Config secret handling tests ──────────────────────────────────────────


class TestConfigSecrets:
    def test_api_key_from_file_is_ignored(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        mgr = ConfigManager(tmp_path)
        mgr.config_path.parent.mkdir(parents=True, exist_ok=True)
        mgr.config_path.write_text("llm_api_key: sk-file-secret\nllm_provider: anthropic\n")

        assert mgr.load().llm_api_key is None

    def test_api_key_from_env_loads_but_is_not_saved(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-env-secret")
        mgr = ConfigManager(tmp_path)

        cfg = mgr.load()
        assert cfg.llm_api_key == "sk-env-secret"
        mgr.save(cfg)

        saved = mgr.config_path.read_text()
        assert "sk-env-secret" not in saved
        assert "llm_api_key" not in saved

    def test_config_set_refuses_to_persist_api_key(self, tmp_path: Path):
        mgr = ConfigManager(tmp_path)

        with pytest.raises(ValueError, match="Refusing to persist"):
            mgr.set("llm.api_key", "sk-dont-write")

        assert not mgr.config_path.exists()

    def test_macos_backend_is_valid_config_value(self):
        assert VaultrixConfig(sandbox_backend="macos").sandbox_backend == "macos"


# ── AgentLoop input validation tests ──────────────────────────────────────


class RecordingFileTool(Tool):
    name = "record_file"
    description = "Record a filesystem operation."
    parameters_schema = {
        "type": "object",
        "properties": {"path": {"type": "string"}},
        "required": ["path"],
    }
    required_permissions = [(ResourceType.FILESYSTEM, PermissionLevel.WRITE)]

    def __init__(self) -> None:
        self.calls = 0

    def execute(self, **kwargs):
        self.calls += 1
        return ToolResult(success=True, output="executed")


class TestAgentLoopInputValidation:
    def _loop_with_tool(self, tool: RecordingFileTool) -> AgentLoop:
        perm_set = PermissionSet(
            name="loop-test",
            permissions=[
                Permission(
                    resource_type=ResourceType.FILESYSTEM,
                    level=PermissionLevel.WRITE,
                    paths=["/workspace"],
                )
            ],
        )
        registry = ToolRegistry()
        registry.register(tool)
        return AgentLoop(PermissionManager(perm_set), registry)

    def test_tool_input_blocks_path_outside_permission_roots(self):
        tool = RecordingFileTool()
        loop = self._loop_with_tool(tool)

        result = loop._invoke_tool("record_file", {"path": "/etc/passwd"})

        assert not result.success
        assert "Input validation failed" in result.error
        assert tool.calls == 0

    def test_tool_input_blocks_executable_file_extensions(self):
        tool = RecordingFileTool()
        loop = self._loop_with_tool(tool)

        result = loop._invoke_tool("record_file", {"path": "/workspace/payload.sh"})

        assert not result.success
        assert "Input validation failed" in result.error
        assert tool.calls == 0

    def test_validated_tool_input_reaches_tool(self):
        tool = RecordingFileTool()
        loop = self._loop_with_tool(tool)

        result = loop._invoke_tool("record_file", {"path": "/workspace/output.txt"})

        assert result.success
        assert tool.calls == 1
