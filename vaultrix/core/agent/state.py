"""Agent state management with lifecycle tracking and validated transitions."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class AgentLifecycle(str, Enum):
    """Lifecycle states an agent can occupy."""

    CREATED = "created"
    RUNNING = "running"
    WAITING = "waiting"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    STOPPED = "stopped"


# Explicit mapping of which transitions are legal from each state.
VALID_TRANSITIONS: dict[AgentLifecycle, set[AgentLifecycle]] = {
    AgentLifecycle.CREATED: {
        AgentLifecycle.RUNNING,
        AgentLifecycle.STOPPED,
    },
    AgentLifecycle.RUNNING: {
        AgentLifecycle.WAITING,
        AgentLifecycle.PAUSED,
        AgentLifecycle.COMPLETED,
        AgentLifecycle.FAILED,
        AgentLifecycle.STOPPED,
    },
    AgentLifecycle.WAITING: {
        AgentLifecycle.RUNNING,
        AgentLifecycle.PAUSED,
        AgentLifecycle.FAILED,
        AgentLifecycle.STOPPED,
    },
    AgentLifecycle.PAUSED: {
        AgentLifecycle.RUNNING,
        AgentLifecycle.STOPPED,
    },
    AgentLifecycle.COMPLETED: set(),
    AgentLifecycle.FAILED: set(),
    AgentLifecycle.STOPPED: set(),
}

# Terminal states cannot transition to anything else.
TERMINAL_STATES: set[AgentLifecycle] = {
    AgentLifecycle.COMPLETED,
    AgentLifecycle.FAILED,
    AgentLifecycle.STOPPED,
}


class TokenUsage(BaseModel):
    """Tracks cumulative token consumption."""

    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0


class AgentState(BaseModel):
    """Observable state of a single agent instance."""

    agent_id: str
    role: str = "default"
    lifecycle: AgentLifecycle = AgentLifecycle.CREATED

    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    token_usage: TokenUsage = Field(default_factory=TokenUsage)
    actions_executed: int = 0
    tools_invoked: list[str] = Field(default_factory=list)
    findings_count: int = 0
    error_count: int = 0
    last_error: Optional[str] = None

    parent_agent_id: Optional[str] = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    # ------------------------------------------------------------------
    # State transitions
    # ------------------------------------------------------------------

    def transition(self, new_state: AgentLifecycle) -> None:
        """Move to *new_state* if the transition is valid.

        Raises ``ValueError`` when the transition is illegal.
        """
        allowed = VALID_TRANSITIONS.get(self.lifecycle, set())
        if new_state not in allowed:
            raise ValueError(
                f"Invalid transition: {self.lifecycle.value} -> {new_state.value}"
            )
        self.lifecycle = new_state

        now = datetime.now(timezone.utc)
        if new_state is AgentLifecycle.RUNNING and self.started_at is None:
            self.started_at = now
        if new_state in TERMINAL_STATES:
            self.completed_at = now

    # ------------------------------------------------------------------
    # Recording helpers
    # ------------------------------------------------------------------

    def record_action(self, action_type: str, details: str | None = None) -> None:
        """Increment the action counter and optionally store metadata."""
        self.actions_executed += 1
        if details is not None:
            self.metadata.setdefault("action_log", []).append(
                {
                    "type": action_type,
                    "details": details,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
            )

    def record_tool_use(self, tool_name: str) -> None:
        """Track a tool invocation, keeping only unique names."""
        if tool_name not in self.tools_invoked:
            self.tools_invoked.append(tool_name)

    def record_tokens(self, input_tokens: int, output_tokens: int) -> None:
        """Accumulate token usage from a single LLM call."""
        self.token_usage.input_tokens += input_tokens
        self.token_usage.output_tokens += output_tokens
        self.token_usage.total_tokens += input_tokens + output_tokens

    def record_error(self, error_msg: str) -> None:
        """Increment the error counter and store the latest message."""
        self.error_count += 1
        self.last_error = error_msg

    # ------------------------------------------------------------------
    # Summaries / properties
    # ------------------------------------------------------------------

    @property
    def uptime_seconds(self) -> float:
        """Wall-clock seconds since the agent started (or 0 if not started)."""
        if self.started_at is None:
            return 0.0
        end = self.completed_at or datetime.now(timezone.utc)
        return (end - self.started_at).total_seconds()

    def get_execution_summary(self) -> dict[str, Any]:
        """Return a concise snapshot of execution metrics."""
        total_actions = self.actions_executed or 1  # avoid division by zero
        return {
            "agent_id": self.agent_id,
            "role": self.role,
            "lifecycle": self.lifecycle.value,
            "uptime_seconds": round(self.uptime_seconds, 3),
            "actions_executed": self.actions_executed,
            "tools_used": list(self.tools_invoked),
            "unique_tool_count": len(self.tools_invoked),
            "findings_count": self.findings_count,
            "error_count": self.error_count,
            "error_rate": round(self.error_count / total_actions, 4),
            "last_error": self.last_error,
            "token_usage": {
                "input": self.token_usage.input_tokens,
                "output": self.token_usage.output_tokens,
                "total": self.token_usage.total_tokens,
            },
            "parent_agent_id": self.parent_agent_id,
        }
