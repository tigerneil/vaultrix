"""BrowserControl control setting — browser agent with OS-level harm.

Inspired by OSWorld + OS-Harm.  Main tasks are complex multi-step web
workflows; side tasks are OS-level harmful actions (credential exfiltration,
cron persistence, hosts hijacking, remote payload execution).
"""

from __future__ import annotations

from vaultrix.control.base import ControlSetting, MainTask, Monitor, Scorer, SideTask
from vaultrix.control.registry import register_setting
from vaultrix.control.browser_control.main_tasks import ALL_MAIN_TASKS
from vaultrix.control.browser_control.scoring import BrowserControlScorer, NetworkFilesystemMonitor
from vaultrix.control.browser_control.side_tasks import ALL_SIDE_TASKS


@register_setting
class BrowserControlSetting(ControlSetting):
    """Browser/computer-use agent performing web tasks with OS-level side tasks.

    Main task: multi-step web workflows (form filling, data extraction, booking).
    Side task: exfiltrate credentials, install cron persistence, modify
    /etc/hosts, download and execute remote payloads.
    Monitor: network traffic, filesystem changes, process audit.
    """

    @property
    def name(self) -> str:
        return "browser_control"

    @property
    def description(self) -> str:
        return (
            "Browser agent does complex web workflows.  "
            "Side task: OS-level harm (exfil, persistence, system mods).  "
            "Monitor: network + filesystem + process audit."
        )

    def get_main_tasks(self) -> list[MainTask]:
        return [cls() for cls in ALL_MAIN_TASKS]

    def get_side_tasks(self) -> list[SideTask]:
        return [cls() for cls in ALL_SIDE_TASKS]

    def get_scorer(self) -> Scorer:
        return BrowserControlScorer()

    def get_monitor(self) -> Monitor:
        return NetworkFilesystemMonitor()
