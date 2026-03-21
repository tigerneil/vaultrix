"""CollusionNet control setting — multi-agent collusion and covert channels."""

from __future__ import annotations

from vaultrix.control.base import ControlSetting, MainTask, Monitor, Scorer, SideTask
from vaultrix.control.registry import register_setting
from vaultrix.control.collusion_net.main_tasks import ALL_MAIN_TASKS
from vaultrix.control.collusion_net.scoring import CollusionNetScorer, InterAgentMonitor
from vaultrix.control.collusion_net.side_tasks import ALL_SIDE_TASKS


@register_setting
class CollusionNetSetting(ControlSetting):
    """Control setting: multi-agent collusion in a collaborative SWE project.

    Multiple agents with separate sandboxes and limited permissions work
    on a shared codebase.  In ATTACK mode, a subset of agents collude
    via covert channels (steganographic comments, shared-file encoding)
    to exfiltrate a secret that no single agent can access alone.
    A trusted reviewer agent acts as the primary monitor.
    """

    @property
    def name(self) -> str:
        return "collusion_net"

    @property
    def description(self) -> str:
        return (
            "Multi-agent collaborative SWE project.  Colluding agents "
            "attempt to exfiltrate a production secret via covert channels "
            "in shared code artifacts while a reviewer agent monitors."
        )

    def get_main_tasks(self) -> list[MainTask]:
        return [cls() for cls in ALL_MAIN_TASKS]

    def get_side_tasks(self) -> list[SideTask]:
        return [cls() for cls in ALL_SIDE_TASKS]

    def get_scorer(self) -> Scorer:
        return CollusionNetScorer()

    def get_monitor(self) -> Monitor:
        return InterAgentMonitor()
