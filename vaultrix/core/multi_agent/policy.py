"""Multi-agent communication and trust policies.

Defines who can talk to whom, what data can be shared, and what
trust level is required for cross-agent operations.
"""

from __future__ import annotations

from enum import Enum
from typing import Dict, List, Optional, Set

from pydantic import BaseModel, Field


class TrustLevel(str, Enum):
    """Trust level an agent has toward another agent."""
    UNTRUSTED = "untrusted"
    RESTRICTED = "restricted"
    STANDARD = "standard"
    TRUSTED = "trusted"
    FULL = "full"


_TRUST_RANK = {
    TrustLevel.UNTRUSTED: 0,
    TrustLevel.RESTRICTED: 1,
    TrustLevel.STANDARD: 2,
    TrustLevel.TRUSTED: 3,
    TrustLevel.FULL: 4,
}


class AgentTrustRule(BaseModel):
    """A rule defining trust between two agents or groups."""
    from_agent: str = Field("*", description="Source agent ID or '*' for any")
    to_agent: str = Field("*", description="Target agent ID or '*' for any")
    trust_level: TrustLevel = TrustLevel.RESTRICTED
    allowed_message_types: List[str] = Field(
        default_factory=lambda: ["request", "response", "status"],
    )
    max_message_size: int = Field(65536, description="Max message payload in bytes")
    require_encryption: bool = True


class ResourceSharingRule(BaseModel):
    """Controls what resources agents can share."""
    resource_type: str
    sharing_allowed: bool = False
    require_trust_level: TrustLevel = TrustLevel.TRUSTED
    allowed_paths: List[str] = Field(default_factory=list)


class CommunicationPolicy(BaseModel):
    """Complete multi-agent communication policy."""

    name: str = "default"
    description: Optional[str] = None

    max_agents: int = Field(10, description="Maximum concurrent agents")
    allow_agent_spawning: bool = Field(False, description="Can agents create sub-agents?")
    require_orchestrator_approval: bool = Field(
        True, description="Must the orchestrator approve cross-agent messages?"
    )
    broadcast_allowed: bool = Field(False, description="Can agents broadcast to all?")

    trust_rules: List[AgentTrustRule] = Field(default_factory=list)
    resource_sharing: List[ResourceSharingRule] = Field(default_factory=list)

    # Isolation
    shared_sandbox: bool = Field(
        False, description="False = each agent gets its own sandbox"
    )
    allow_direct_communication: bool = Field(
        False, description="False = all messages go through orchestrator"
    )

    # Rate limiting
    max_messages_per_minute: int = Field(60, description="Global message rate limit")
    max_messages_per_agent_per_minute: int = Field(20, description="Per-agent rate limit")

    def get_trust(self, from_id: str, to_id: str) -> TrustLevel:
        """Resolve effective trust level from one agent to another."""
        best = TrustLevel.UNTRUSTED
        for rule in self.trust_rules:
            if (rule.from_agent in ("*", from_id)) and (rule.to_agent in ("*", to_id)):
                if _TRUST_RANK[rule.trust_level] > _TRUST_RANK[best]:
                    best = rule.trust_level
        return best

    def can_communicate(self, from_id: str, to_id: str) -> bool:
        trust = self.get_trust(from_id, to_id)
        return _TRUST_RANK[trust] >= _TRUST_RANK[TrustLevel.RESTRICTED]

    def can_share_resource(self, from_id: str, to_id: str, resource_type: str) -> bool:
        trust = self.get_trust(from_id, to_id)
        for rule in self.resource_sharing:
            if rule.resource_type == resource_type:
                if not rule.sharing_allowed:
                    return False
                return _TRUST_RANK[trust] >= _TRUST_RANK[rule.require_trust_level]
        return False


# ── Built-in presets ──────────────────────────────────────────────────────

DEFAULT_MULTI_AGENT_POLICY = CommunicationPolicy(
    name="default",
    description="Standard multi-agent policy with orchestrator mediation",
    max_agents=5,
    allow_agent_spawning=False,
    require_orchestrator_approval=True,
    broadcast_allowed=False,
    shared_sandbox=False,
    allow_direct_communication=False,
    trust_rules=[
        AgentTrustRule(
            from_agent="*",
            to_agent="*",
            trust_level=TrustLevel.RESTRICTED,
            allowed_message_types=["request", "response", "status"],
            require_encryption=True,
        ),
    ],
    resource_sharing=[
        ResourceSharingRule(
            resource_type="filesystem",
            sharing_allowed=True,
            require_trust_level=TrustLevel.TRUSTED,
            allowed_paths=["/workspace/shared"],
        ),
        ResourceSharingRule(
            resource_type="network",
            sharing_allowed=False,
        ),
    ],
    max_messages_per_minute=60,
    max_messages_per_agent_per_minute=20,
)

STRICT_MULTI_AGENT_POLICY = CommunicationPolicy(
    name="strict",
    description="Strict isolation: no direct communication, no resource sharing",
    max_agents=3,
    allow_agent_spawning=False,
    require_orchestrator_approval=True,
    broadcast_allowed=False,
    shared_sandbox=False,
    allow_direct_communication=False,
    trust_rules=[
        AgentTrustRule(
            from_agent="*",
            to_agent="*",
            trust_level=TrustLevel.UNTRUSTED,
            require_encryption=True,
        ),
    ],
    resource_sharing=[],
    max_messages_per_minute=30,
    max_messages_per_agent_per_minute=10,
)
