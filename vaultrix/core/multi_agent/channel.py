"""Secure inter-agent communication channel.

All messages between agents are routed through a SecureChannel which
enforces policy, encrypts payloads, and maintains an audit trail.
"""

from __future__ import annotations

import collections
import logging
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

from vaultrix.core.encryption.manager import EncryptionManager
from vaultrix.core.multi_agent.policy import CommunicationPolicy, TrustLevel, _TRUST_RANK

logger = logging.getLogger(__name__)


class MessageType(str, Enum):
    REQUEST = "request"
    RESPONSE = "response"
    STATUS = "status"
    DELEGATE = "delegate"
    RESULT = "result"
    ERROR = "error"


@dataclass
class Message:
    """A single inter-agent message."""
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    from_agent: str = ""
    to_agent: str = ""
    message_type: MessageType = MessageType.REQUEST
    payload: Dict[str, Any] = field(default_factory=dict)
    encrypted: bool = False
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    parent_id: Optional[str] = None


class ChannelViolation(Exception):
    """Raised when a message violates communication policy."""


OnMessageCallback = Callable[[Message, str], None]  # (message, verdict)


class SecureChannel:
    """Mediates all inter-agent communication.

    Responsibilities:
    - Policy enforcement (trust, rate limits, message types)
    - Payload encryption/decryption
    - Audit logging
    - Delivery to recipient queues
    """

    def __init__(
        self,
        policy: CommunicationPolicy,
        encryption: Optional[EncryptionManager] = None,
        on_message: Optional[OnMessageCallback] = None,
    ) -> None:
        self.policy = policy
        self._enc = encryption
        self.on_message = on_message

        # Per-agent inboxes
        self._queues: Dict[str, List[Message]] = {}
        # Audit trail
        self.audit_log: List[Dict[str, Any]] = []
        # Rate limit tracking
        self._global_rate: collections.deque = collections.deque()
        self._agent_rates: Dict[str, collections.deque] = {}

    def register_agent(self, agent_id: str) -> None:
        self._queues.setdefault(agent_id, [])
        self._agent_rates.setdefault(agent_id, collections.deque())

    def unregister_agent(self, agent_id: str) -> None:
        self._queues.pop(agent_id, None)
        self._agent_rates.pop(agent_id, None)

    def send(self, message: Message) -> None:
        """Send a message through the channel with full policy checks."""
        # 1. Sender must be registered
        if message.from_agent not in self._queues:
            raise ChannelViolation(f"Unknown sender: {message.from_agent}")

        # 2. Recipient must be registered (or broadcast)
        if message.to_agent not in self._queues:
            if not (message.to_agent == "*" and self.policy.broadcast_allowed):
                raise ChannelViolation(f"Unknown recipient: {message.to_agent}")

        # 3. Trust check
        if not self.policy.can_communicate(message.from_agent, message.to_agent):
            self._audit(message, "DENIED:trust")
            raise ChannelViolation(
                f"Communication denied: {message.from_agent} -> {message.to_agent}"
            )

        # 4. Message type check
        trust = self.policy.get_trust(message.from_agent, message.to_agent)
        allowed_types = self._allowed_types(message.from_agent, message.to_agent)
        if message.message_type.value not in allowed_types:
            self._audit(message, "DENIED:type")
            raise ChannelViolation(
                f"Message type {message.message_type.value} not allowed"
            )

        # 5. Rate limiting
        if not self._check_rate(message.from_agent):
            self._audit(message, "DENIED:rate_limit")
            raise ChannelViolation("Rate limit exceeded")

        # 6. Size check
        import json
        payload_size = len(json.dumps(message.payload, default=str).encode())
        max_size = self._max_message_size(message.from_agent, message.to_agent)
        if payload_size > max_size:
            self._audit(message, "DENIED:size")
            raise ChannelViolation(
                f"Payload too large: {payload_size} > {max_size}"
            )

        # 7. Encrypt if required
        if self._requires_encryption(message.from_agent, message.to_agent):
            if self._enc:
                encrypted_payload = self._enc.encrypt_json(message.payload)
                message.payload = {"__encrypted__": encrypted_payload.decode()}
                message.encrypted = True

        # 8. Deliver
        if message.to_agent == "*":
            for aid in self._queues:
                if aid != message.from_agent:
                    self._queues[aid].append(message)
        else:
            self._queues[message.to_agent].append(message)

        self._audit(message, "DELIVERED")
        if self.on_message:
            self.on_message(message, "DELIVERED")

    def receive(self, agent_id: str) -> List[Message]:
        """Drain and return all pending messages for an agent."""
        msgs = list(self._queues.get(agent_id, []))
        self._queues[agent_id] = []

        # Decrypt if needed
        if self._enc:
            for msg in msgs:
                if msg.encrypted and "__encrypted__" in msg.payload:
                    raw = msg.payload["__encrypted__"]
                    msg.payload = self._enc.decrypt_json(raw.encode())
                    msg.encrypted = False

        return msgs

    def get_audit_log(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        if limit:
            return self.audit_log[-limit:]
        return list(self.audit_log)

    # -- internals --

    def _allowed_types(self, from_id: str, to_id: str) -> List[str]:
        for rule in self.policy.trust_rules:
            if (rule.from_agent in ("*", from_id)) and (rule.to_agent in ("*", to_id)):
                return rule.allowed_message_types
        return []

    def _max_message_size(self, from_id: str, to_id: str) -> int:
        for rule in self.policy.trust_rules:
            if (rule.from_agent in ("*", from_id)) and (rule.to_agent in ("*", to_id)):
                return rule.max_message_size
        return 0

    def _requires_encryption(self, from_id: str, to_id: str) -> bool:
        for rule in self.policy.trust_rules:
            if (rule.from_agent in ("*", from_id)) and (rule.to_agent in ("*", to_id)):
                return rule.require_encryption
        return True

    def _check_rate(self, agent_id: str) -> bool:
        now = time.monotonic()
        # Global rate
        while self._global_rate and self._global_rate[0] < now - 60:
            self._global_rate.popleft()
        if len(self._global_rate) >= self.policy.max_messages_per_minute:
            return False
        self._global_rate.append(now)

        # Per-agent rate
        bucket = self._agent_rates.setdefault(agent_id, collections.deque())
        while bucket and bucket[0] < now - 60:
            bucket.popleft()
        if len(bucket) >= self.policy.max_messages_per_agent_per_minute:
            return False
        bucket.append(now)
        return True

    def _audit(self, msg: Message, verdict: str) -> None:
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "message_id": msg.id,
            "from": msg.from_agent,
            "to": msg.to_agent,
            "type": msg.message_type.value,
            "verdict": verdict,
            "encrypted": msg.encrypted,
        }
        self.audit_log.append(entry)
        if len(self.audit_log) > 5000:
            self.audit_log = self.audit_log[-5000:]
        logger.debug("Channel: %s %s->%s [%s]", verdict, msg.from_agent, msg.to_agent, msg.message_type.value)
