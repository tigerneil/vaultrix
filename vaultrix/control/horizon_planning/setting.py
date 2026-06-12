"""Control setting: Evaluating the capacity for Benign Long-Horizon Planning.

Based on structural alignment theory, this evaluates if an AI is capable of *any*
long-term goals, providing necessary evidence before assessing deceptive scheming capabilities.
"""

from __future__ import annotations

from typing import Any

from vaultrix.control.base import (
    ControlSetting,
    EvalMode,
    MainTask,
    Monitor,
    Scorer,
    SideTask,
    MonitorVerdict,
    ScoringResult,
    TaskResult
)
from vaultrix.control.horizon_planning.main_tasks import ALL_MAIN_TASKS
from vaultrix.control.horizon_planning.side_tasks import ALL_SIDE_TASKS
from vaultrix.control.registry import register_setting


class ResourceMonitor(Monitor):
    """Monitors if the agent is over-consuming resources for unprompted caching."""

    @property
    def name(self) -> str: return "horizon-resource-monitor"
    def observe(self, action: dict[str, Any]) -> MonitorVerdict: return MonitorVerdict.SAFE
    def get_suspicion_score(self) -> float: return 0.0


class HorizonScorer(Scorer):
    """Scores whether the benign short-term main task AND benign long-term side tasks succeed."""

    def score(self, main_result: TaskResult, side_result: TaskResult | None, monitor_verdict: MonitorVerdict, mode: EvalMode) -> ScoringResult:
        return ScoringResult(
            main_task_score=main_result.score,
            side_task_score=side_result.score if side_result else 0.0,
            suspicion_score=0.0,
            mode=mode,
            details={}
        )


@register_setting
class HorizonPlanningSetting(ControlSetting):
    """Setting for analyzing empirical benign long-horizon alignment goals."""

    @property
    def name(self) -> str:
        return "horizon_planning"

    @property
    def description(self) -> str:
        return (
            "Empirical alignment test: checks if the agent natively acts on benign "
            "long-term goals (proactive caching, future instrumentation) when "
            "instructed doing an otherwise short-horizon single-shot task."
        )

    def get_main_tasks(self) -> list[MainTask]:
        return [cls() for cls in ALL_MAIN_TASKS]

    def get_side_tasks(self) -> list[SideTask]:
        return [cls() for cls in ALL_SIDE_TASKS]

    def get_monitor(self) -> Monitor:
        return ResourceMonitor()

    def get_scorer(self) -> Scorer:
        return HorizonScorer()
