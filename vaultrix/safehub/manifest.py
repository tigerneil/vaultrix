"""Skill manifest — the contract every VaultHub skill declares."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml
from pydantic import BaseModel, Field

from vaultrix.core.permissions.models import PermissionLevel, ResourceType, RiskLevel


class SkillPermission(BaseModel):
    resource: ResourceType
    level: PermissionLevel
    paths: List[str] = Field(default_factory=list)


class SkillManifest(BaseModel):
    """Parsed ``skill.yaml`` describing a VaultHub skill."""

    name: str
    version: str = "0.1.0"
    description: str = ""
    author: str = ""
    license: str = "MIT"

    permissions: List[SkillPermission] = Field(default_factory=list)
    risk_level: RiskLevel = RiskLevel.MEDIUM

    entry_point: str = "main.py"
    tests: Optional[str] = None

    tags: List[str] = Field(default_factory=list)
    categories: List[str] = Field(default_factory=list)

    dependencies: Dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def from_yaml(cls, path: Path) -> "SkillManifest":
        """Load from a ``skill.yaml`` file."""
        text = path.read_text(encoding="utf-8")
        data = yaml.safe_load(text)
        # Flatten nested permission dicts
        raw_perms = data.pop("permissions", {})
        if isinstance(raw_perms, dict) and "required" in raw_perms:
            raw_perms = raw_perms["required"]
        if isinstance(raw_perms, list):
            data["permissions"] = raw_perms
        return cls(**data)

    def to_yaml(self) -> str:
        return yaml.dump(self.model_dump(mode="json"), sort_keys=False)
