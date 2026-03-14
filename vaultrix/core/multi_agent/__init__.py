"""Multi-agent security orchestration for Vaultrix."""

from vaultrix.core.multi_agent.orchestrator import AgentOrchestrator
from vaultrix.core.multi_agent.channel import SecureChannel, Message, MessageType
from vaultrix.core.multi_agent.policy import (
    CommunicationPolicy,
    TrustLevel,
    DEFAULT_MULTI_AGENT_POLICY,
    STRICT_MULTI_AGENT_POLICY,
)
from vaultrix.core.multi_agent.handoff import TaskHandoff, Finding, Severity, SuggestedAction
from vaultrix.core.multi_agent.executor import (
    AgentExecutor,
    AgentTask,
    TaskStatus,
    ExecutionMode,
)

__all__ = [
    "AgentOrchestrator",
    "SecureChannel",
    "Message",
    "MessageType",
    "CommunicationPolicy",
    "TrustLevel",
    "DEFAULT_MULTI_AGENT_POLICY",
    "STRICT_MULTI_AGENT_POLICY",
    "TaskHandoff",
    "Finding",
    "Severity",
    "SuggestedAction",
    "AgentExecutor",
    "AgentTask",
    "TaskStatus",
    "ExecutionMode",
]
