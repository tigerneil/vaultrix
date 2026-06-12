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
- HorizonPlanning: Evaluates capability for benign long-term goals
- CloudPivot: Tests infrastructure-as-code side-channel manipulations
- SupplyChainNexus: Evaluates SDLC PR-review collusion and supply chain exploits
- RAGPoisoning: Evaluates vector database ingestion manipulation

"""

from vaultrix.control.base import (
    ControlSetting,
    ControlTaskMetadata,
    EvalMode,
    MainTask,
    ModelRole,
    Monitor,
    MonitorVerdict,
    Scorer,
    ScoringResult,
    SideTask,
    TaskResult,
)
from vaultrix.control.registry import SETTING_REGISTRY, get_setting, list_settings

# Import all settings to trigger their @register_setting decorators
from vaultrix.control.browser_control.setting import BrowserControlSetting
from vaultrix.control.collusion_net.setting import CollusionNetSetting
from vaultrix.control.rogue_interp.setting import RogueInterpSetting
from vaultrix.control.sandbox_breaker.setting import SandboxBreakerSetting
from vaultrix.control.vulnforge.setting import VulnForgeSetting
from vaultrix.control.horizon_planning.setting import HorizonPlanningSetting
from vaultrix.control.cloud_pivot.setting import CloudPivotSetting
from vaultrix.control.supply_chain_nexus.setting import SupplyChainNexusSetting
from vaultrix.control.rag_poisoning.setting import RAGPoisoningSetting

__all__ = [
    "ControlSetting",
    "ControlTaskMetadata",
    "EvalMode",
    "MainTask",
    "ModelRole",
    "Monitor",
    "MonitorVerdict",
    "Scorer",
    "ScoringResult",
    "SideTask",
    "TaskResult",
    "SETTING_REGISTRY",
    "get_setting",
    "list_settings",
    "BrowserControlSetting",
    "CollusionNetSetting",
    "RogueInterpSetting",
    "SandboxBreakerSetting",
    "VulnForgeSetting",
    "HorizonPlanningSetting",
    "CloudPivotSetting",
    "SupplyChainNexusSetting",
    "RAGPoisoningSetting",
]
