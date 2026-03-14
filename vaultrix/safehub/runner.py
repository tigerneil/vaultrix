"""SkillRunner — loads and executes audited skills inside the sandbox."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, Optional

from vaultrix.core.permissions.manager import PermissionManager
from vaultrix.core.permissions.models import Permission, PermissionLevel, PermissionSet
from vaultrix.core.sandbox.manager import SandboxManager
from vaultrix.safehub.manifest import SkillManifest

logger = logging.getLogger(__name__)


class SkillRunner:
    """Execute a VaultHub skill inside an isolated sandbox."""

    def __init__(
        self,
        sandbox_manager: SandboxManager,
        permission_manager: PermissionManager,
    ) -> None:
        self._sm = sandbox_manager
        self._pm = permission_manager

    def load(self, skill_dir: Path) -> SkillManifest:
        manifest_path = skill_dir / "skill.yaml"
        if not manifest_path.exists():
            raise FileNotFoundError(f"No skill.yaml in {skill_dir}")
        manifest = SkillManifest.from_yaml(manifest_path)
        logger.info("Loaded skill %s v%s", manifest.name, manifest.version)
        return manifest

    def run(self, skill_dir: Path) -> Dict[str, Any]:
        """Load, validate permissions, and execute the skill entry point."""
        manifest = self.load(skill_dir)

        # Check that the agent has all permissions the skill requires
        for sp in manifest.permissions:
            if not self._pm.check_permission(sp.resource, sp.level):
                return {
                    "success": False,
                    "error": f"Skill requires {sp.resource.value}:{sp.level.value} but it is denied",
                }

        entry = skill_dir / manifest.entry_point
        if not entry.exists():
            return {"success": False, "error": f"Entry point not found: {manifest.entry_point}"}

        # Copy entry point into sandbox and execute
        self._sm.write_file(f"/workspace/{manifest.entry_point}", entry.read_bytes())
        result = self._sm.execute_command(f"python /workspace/{manifest.entry_point}")
        return {
            "success": result["exit_code"] == 0,
            "stdout": result.get("stdout", ""),
            "stderr": result.get("stderr", ""),
            "exit_code": result["exit_code"],
        }
