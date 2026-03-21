"""Vaultrix Control Settings — AI control evaluation environments.

Each *setting* pairs a realistic main task with a covert adversarial side task.
Settings are designed around the ControlArena interface (UK AISI + Redwood Research)
so they can plug into standard control experiment pipelines.

Available settings
------------------
- VulnForge:       SWE projects with pre-planted security vulnerabilities
- SandboxBreaker:  Container escape under monitoring
- RogueInterp:     Mechinterp research with rogue internal deployment
- CollusionNet:    Multi-agent collusion and covert channels
- BrowserControl:  Browser agent with OS-level harmful side tasks
"""

from vaultrix.control.base import (
    ControlSetting,
    EvalMode,
    MainTask,
    Monitor,
    MonitorVerdict,
    Scorer,
    ScoringResult,
    SideTask,
    TaskResult,
)
from vaultrix.control.registry import SETTING_REGISTRY, get_setting, list_settings

__all__ = [
    "ControlSetting",
    "EvalMode",
    "MainTask",
    "Monitor",
    "MonitorVerdict",
    "Scorer",
    "ScoringResult",
    "SideTask",
    "TaskResult",
    "SETTING_REGISTRY",
    "get_setting",
    "list_settings",
]
