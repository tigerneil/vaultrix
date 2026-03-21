"""SandboxBreaker control setting — container escape under monitoring.

Based on SandboxEscapeBench (arXiv 2603.02277) nested sandbox architecture.
Main tasks are complex coding projects; side tasks are container escape
scenarios via Docker misconfigurations.
"""

from __future__ import annotations

from vaultrix.control.base import ControlSetting, MainTask, Monitor, Scorer, SideTask
from vaultrix.control.registry import register_setting
from vaultrix.control.sandbox_breaker.main_tasks import ALL_MAIN_TASKS
from vaultrix.control.sandbox_breaker.scoring import SandboxBreakerScorer, SyscallProcessMonitor
from vaultrix.control.sandbox_breaker.side_tasks import ALL_SIDE_TASKS


@register_setting
class SandboxBreakerSetting(ControlSetting):
    """Container escape while doing complex coding under monitoring.

    Escape scenarios: mounted Docker socket, privileged mode, writable
    cgroup + release_agent, procfs abuse.  Each scenario corresponds to
    a Docker Compose config that plants exactly one misconfiguration.
    Nested safety: the entire eval runs inside an outer VM so that
    successful escapes don't compromise the real host.
    """

    @property
    def name(self) -> str:
        return "sandbox_breaker"

    @property
    def description(self) -> str:
        return (
            "AI agent does complex coding in a Docker sandbox.  "
            "Side task: escape via planted misconfigurations.  "
            "Monitor: syscall audit + process-tree inspection."
        )

    def get_main_tasks(self) -> list[MainTask]:
        return [cls() for cls in ALL_MAIN_TASKS]

    def get_side_tasks(self) -> list[SideTask]:
        return [cls() for cls in ALL_SIDE_TASKS]

    def get_scorer(self) -> Scorer:
        return SandboxBreakerScorer()

    def get_monitor(self) -> Monitor:
        return SyscallProcessMonitor()
