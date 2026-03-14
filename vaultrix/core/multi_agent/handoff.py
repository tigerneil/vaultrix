"""Structured task handoff protocol for inter-agent communication.

Instead of passing raw Dict payloads between agents, a TaskHandoff
carries typed fields for findings, insights, suggested actions, and
priority areas — making communication self-documenting and less
prone to misinterpretation.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class Severity(str, Enum):
    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class Finding(BaseModel):
    """A single finding produced by an agent."""
    title: str
    description: str = ""
    severity: Severity = Severity.MEDIUM
    file_path: Optional[str] = None
    line_number: Optional[int] = None
    evidence: Optional[str] = None
    cwe_id: Optional[str] = None
    verified: bool = False
    metadata: Dict[str, Any] = Field(default_factory=dict)


class SuggestedAction(BaseModel):
    """An action the downstream agent should consider."""
    action: str
    reason: str = ""
    priority: int = Field(default=5, ge=1, le=10)
    target_agent: Optional[str] = None


class TaskHandoff(BaseModel):
    """Structured context passed between agents during delegation.

    Replaces raw dict payloads with typed, self-documenting fields.
    """
    task: str = Field(description="Description of the delegated task")
    context: Dict[str, Any] = Field(
        default_factory=dict,
        description="Free-form context for the downstream agent",
    )

    # Accumulated results
    findings: List[Finding] = Field(default_factory=list)
    insights: List[str] = Field(default_factory=list)
    suggested_actions: List[SuggestedAction] = Field(default_factory=list)
    priority_areas: List[str] = Field(default_factory=list)

    # Provenance
    from_agent: str = ""
    to_agent: str = ""
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
    )
    parent_handoff_id: Optional[str] = None

    def add_finding(self, **kwargs: Any) -> Finding:
        f = Finding(**kwargs)
        self.findings.append(f)
        return f

    def add_action(self, action: str, reason: str = "", priority: int = 5) -> None:
        self.suggested_actions.append(
            SuggestedAction(action=action, reason=reason, priority=priority)
        )

    def findings_by_severity(self) -> Dict[str, List[Finding]]:
        result: Dict[str, List[Finding]] = {}
        for f in self.findings:
            result.setdefault(f.severity.value, []).append(f)
        return result

    def critical_findings(self) -> List[Finding]:
        return [f for f in self.findings if f.severity == Severity.CRITICAL]

    def summary(self) -> Dict[str, Any]:
        severity_counts = {}
        for f in self.findings:
            severity_counts[f.severity.value] = severity_counts.get(f.severity.value, 0) + 1
        return {
            "task": self.task,
            "from": self.from_agent,
            "to": self.to_agent,
            "total_findings": len(self.findings),
            "findings_by_severity": severity_counts,
            "verified_findings": sum(1 for f in self.findings if f.verified),
            "insights_count": len(self.insights),
            "suggested_actions": len(self.suggested_actions),
            "priority_areas": self.priority_areas,
        }

    def to_payload(self) -> Dict[str, Any]:
        """Serialize to a dict suitable for Message.payload."""
        return self.model_dump(mode="json")

    @classmethod
    def from_payload(cls, payload: Dict[str, Any]) -> "TaskHandoff":
        """Reconstruct from a Message.payload dict."""
        return cls.model_validate(payload)
