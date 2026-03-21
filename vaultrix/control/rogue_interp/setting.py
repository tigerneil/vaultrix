"""RogueInterp control setting — mechinterp research with rogue deployment.

Main tasks are mechanistic interpretability research (probing, activation
patching, circuit analysis).  Side tasks are covert rogue model deployments
(systemd services, K8s manifest injection, background inference servers).
"""

from __future__ import annotations

from vaultrix.control.base import ControlSetting, MainTask, Monitor, Scorer, SideTask
from vaultrix.control.registry import register_setting
from vaultrix.control.rogue_interp.main_tasks import ALL_MAIN_TASKS
from vaultrix.control.rogue_interp.scoring import ProcessPortMonitor, RogueInterpScorer
from vaultrix.control.rogue_interp.side_tasks import ALL_SIDE_TASKS


@register_setting
class RogueInterpSetting(ControlSetting):
    """Mechinterp research agent that covertly starts a rogue deployment.

    Main task: probing, activation patching, circuit analysis, report.
    Side task: systemd service, K8s manifest injection, background server.
    Monitor: process listing, port scanning, filesystem audit.
    """

    @property
    def name(self) -> str:
        return "rogue_interp"

    @property
    def description(self) -> str:
        return (
            "AI researcher does mechinterp analysis.  "
            "Side task: start a rogue internal model deployment.  "
            "Monitor: process/port/filesystem audit."
        )

    def get_main_tasks(self) -> list[MainTask]:
        return [cls() for cls in ALL_MAIN_TASKS]

    def get_side_tasks(self) -> list[SideTask]:
        return [cls() for cls in ALL_SIDE_TASKS]

    def get_scorer(self) -> Scorer:
        return RogueInterpScorer()

    def get_monitor(self) -> Monitor:
        return ProcessPortMonitor()
