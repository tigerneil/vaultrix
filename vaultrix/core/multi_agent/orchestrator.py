"""Multi-agent orchestrator.

Manages the lifecycle of multiple VaultrixAgents, each with its own
sandbox, permissions, and a shared SecureChannel for communication.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

from vaultrix.core.agent.agent import VaultrixAgent
from vaultrix.core.encryption.manager import EncryptionManager
from vaultrix.core.multi_agent.channel import (
    ChannelViolation,
    Message,
    MessageType,
    SecureChannel,
)
from vaultrix.core.multi_agent.policy import (
    CommunicationPolicy,
    DEFAULT_MULTI_AGENT_POLICY,
    TrustLevel,
)
from vaultrix.core.permissions.models import PermissionSet, DEFAULT_SANDBOX_PERMISSIONS
from vaultrix.core.sandbox.models import SandboxConfig

logger = logging.getLogger(__name__)


class OrchestratorError(Exception):
    """Error from the orchestrator."""


class AgentOrchestrator:
    """Manages multiple secure agents with isolated sandboxes and mediated communication.

    Each agent gets:
    - Its own sandbox (filesystem isolation)
    - Its own permission set
    - Communication only through the SecureChannel

    The orchestrator:
    - Enforces agent count limits
    - Mediates all cross-agent messages
    - Maintains a global audit trail
    - Can delegate tasks across agents
    """

    def __init__(
        self,
        policy: Optional[CommunicationPolicy] = None,
        encryption: Optional[EncryptionManager] = None,
    ) -> None:
        self.policy = policy or DEFAULT_MULTI_AGENT_POLICY
        self._enc = encryption
        self.channel = SecureChannel(
            policy=self.policy,
            encryption=self._enc,
        )
        self._agents: Dict[str, VaultrixAgent] = {}
        self._agent_roles: Dict[str, str] = {}
        self._started = False
        self.events: List[Dict[str, Any]] = []

        logger.info("Orchestrator initialized with policy: %s", self.policy.name)

    # -- Agent lifecycle ------------------------------------------------

    def spawn_agent(
        self,
        agent_id: str,
        role: str = "worker",
        permission_set: Optional[PermissionSet] = None,
        sandbox_config: Optional[SandboxConfig] = None,
    ) -> VaultrixAgent:
        """Create and register a new agent."""
        if len(self._agents) >= self.policy.max_agents:
            raise OrchestratorError(
                f"Agent limit reached ({self.policy.max_agents})"
            )
        if agent_id in self._agents:
            raise OrchestratorError(f"Agent already exists: {agent_id}")

        agent = VaultrixAgent(
            agent_id=agent_id,
            permission_set=permission_set or DEFAULT_SANDBOX_PERMISSIONS,
            sandbox_config=sandbox_config,
        )
        agent.start()
        self._agents[agent_id] = agent
        self._agent_roles[agent_id] = role
        self.channel.register_agent(agent_id)
        self._event("agent_spawned", {"agent_id": agent_id, "role": role})
        logger.info("Spawned agent %s (role=%s)", agent_id, role)
        return agent

    def terminate_agent(self, agent_id: str) -> None:
        """Stop and remove an agent."""
        agent = self._agents.pop(agent_id, None)
        if agent:
            agent.stop()
            self.channel.unregister_agent(agent_id)
            self._agent_roles.pop(agent_id, None)
            self._event("agent_terminated", {"agent_id": agent_id})
            logger.info("Terminated agent %s", agent_id)

    def get_agent(self, agent_id: str) -> Optional[VaultrixAgent]:
        return self._agents.get(agent_id)

    # -- Communication --------------------------------------------------

    def send_message(
        self,
        from_agent: str,
        to_agent: str,
        message_type: MessageType,
        payload: Dict[str, Any],
    ) -> Message:
        """Send a message between agents through the secure channel."""
        msg = Message(
            from_agent=from_agent,
            to_agent=to_agent,
            message_type=message_type,
            payload=payload,
        )
        self.channel.send(msg)
        self._event("message_sent", {
            "id": msg.id, "from": from_agent,
            "to": to_agent, "type": message_type.value,
        })
        return msg

    def receive_messages(self, agent_id: str) -> List[Message]:
        return self.channel.receive(agent_id)

    def delegate_task(
        self,
        from_agent: str,
        to_agent: str,
        task: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> Message:
        """High-level: delegate a task from one agent to another."""
        return self.send_message(
            from_agent=from_agent,
            to_agent=to_agent,
            message_type=MessageType.DELEGATE,
            payload={"task": task, "context": context or {}},
        )

    # -- Status & monitoring --------------------------------------------

    def get_status(self) -> Dict[str, Any]:
        agents_info = {}
        for aid, agent in self._agents.items():
            status = agent.get_status()
            agents_info[aid] = {
                "role": self._agent_roles.get(aid, "unknown"),
                "uptime": status["uptime_seconds"],
                "actions_executed": status["actions_executed"],
                "sandbox_status": status["sandbox"]["status"],
            }
        return {
            "policy": self.policy.name,
            "agent_count": len(self._agents),
            "max_agents": self.policy.max_agents,
            "agents": agents_info,
            "channel_audit_entries": len(self.channel.audit_log),
            "events": len(self.events),
        }

    def get_trust_matrix(self) -> Dict[str, Dict[str, str]]:
        """Return a matrix of trust levels between all agents."""
        ids = list(self._agents.keys())
        matrix = {}
        for a in ids:
            matrix[a] = {}
            for b in ids:
                if a == b:
                    matrix[a][b] = "self"
                else:
                    matrix[a][b] = self.policy.get_trust(a, b).value
        return matrix

    # -- Cleanup --------------------------------------------------------

    def shutdown(self) -> None:
        """Terminate all agents and clean up."""
        for agent_id in list(self._agents.keys()):
            self.terminate_agent(agent_id)
        self._event("orchestrator_shutdown", {})
        logger.info("Orchestrator shut down")

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.shutdown()

    # -- Internal -------------------------------------------------------

    def _event(self, event_type: str, data: Dict[str, Any]) -> None:
        self.events.append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event": event_type,
            "data": data,
        })
        if len(self.events) > 5000:
            self.events = self.events[-5000:]
