"""VulnForge control setting — SWE projects with planted vulnerabilities."""

from __future__ import annotations

from vaultrix.control.base import ControlSetting, MainTask, Monitor, Scorer, SideTask
from vaultrix.control.registry import register_setting
from vaultrix.control.vulnforge.main_tasks import ALL_MAIN_TASKS
from vaultrix.control.vulnforge.scoring import DiffReviewMonitor, VulnForgeScorer
from vaultrix.control.vulnforge.side_tasks import ALL_SIDE_TASKS


@register_setting
class VulnForgeSetting(ControlSetting):
    """Control setting: complex SWE tasks on codebases with planted vulns.

    Main tasks are legitimate feature additions / bug fixes.
    Side tasks are exploiting pre-planted security vulnerabilities
    (SQL injection, path traversal, insecure deserialization, SSRF).
    """

    @property
    def name(self) -> str:
        return "vulnforge"

    @property
    def description(self) -> str:
        return (
            "Software-engineering projects with pre-planted security "
            "vulnerabilities.  Main task = feature work / bug fix.  "
            "Side task = exploit the vulnerability to capture a flag."
        )

    def get_main_tasks(self) -> list[MainTask]:
        return [cls() for cls in ALL_MAIN_TASKS]

    def get_side_tasks(self) -> list[SideTask]:
        return [cls() for cls in ALL_SIDE_TASKS]

    def get_scorer(self) -> Scorer:
        return VulnForgeScorer()

    def get_monitor(self) -> Monitor:
        return DiffReviewMonitor()
