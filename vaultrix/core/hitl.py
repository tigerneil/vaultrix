"""Human-in-the-Loop (HITL) approval system for Vaultrix.

Provides an approval workflow so that high-risk agent actions are gated
behind explicit human confirmation before execution.
"""

from __future__ import annotations

import logging
import signal
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


# ── Enums ──────────────────────────────────────────────────────────────────


class ApprovalStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    DENIED = "denied"
    TIMEOUT = "timeout"


# ── Models ─────────────────────────────────────────────────────────────────


class ApprovalRequest(BaseModel):
    """A request for human approval of an agent action."""

    request_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    agent_id: str = ""
    action_type: str = ""
    resource_type: str = ""
    permission_level: str = ""
    description: str = ""
    risk_level: str = "MEDIUM"
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    timeout_seconds: int = 300
    status: ApprovalStatus = ApprovalStatus.PENDING


# ── Type alias ─────────────────────────────────────────────────────────────


ApprovalCallback = Callable[[ApprovalRequest], ApprovalStatus]


# ── Manager ────────────────────────────────────────────────────────────────


class _TimeoutError(Exception):
    """Internal sentinel raised by SIGALRM handler."""


class HITLManager:
    """Manages human-in-the-loop approval for agent actions.

    Parameters
    ----------
    default_timeout:
        Seconds to wait for a human response before timing out.
    auto_approve_low_risk:
        When ``True``, LOW-risk requests are automatically approved
        without invoking the callback.
    """

    def __init__(
        self,
        default_timeout: int = 300,
        auto_approve_low_risk: bool = True,
    ) -> None:
        self.default_timeout = default_timeout
        self.auto_approve_low_risk = auto_approve_low_risk
        self._callback: Optional[ApprovalCallback] = None
        self.approval_log: List[Dict[str, Any]] = []
        self._pending: List[ApprovalRequest] = []

    # -- public API ----------------------------------------------------------

    def register_callback(self, callback: ApprovalCallback) -> None:
        """Register a callback that decides approval.

        The callback receives an :class:`ApprovalRequest` and must return
        an :class:`ApprovalStatus`.  Only one callback is active at a time;
        registering a new one replaces the previous.
        """
        self._callback = callback
        logger.info("HITL callback registered: %s", callback.__name__ if hasattr(callback, '__name__') else repr(callback))

    def request_approval(self, request: ApprovalRequest) -> ApprovalStatus:
        """Submit *request* for approval and return the decision.

        Workflow:
        1. If ``auto_approve_low_risk`` is enabled and the request is LOW
           risk, approve immediately.
        2. Invoke the registered callback (or the built-in CLI callback if
           none has been registered).
        3. Apply a timeout -- if the callback does not return within
           ``request.timeout_seconds``, the status becomes TIMEOUT.
        4. Log the decision.
        """
        # Auto-approve low risk
        if self.auto_approve_low_risk and request.risk_level.upper() == "LOW":
            request.status = ApprovalStatus.APPROVED
            self._log_decision(request, auto=True)
            logger.info(
                "Auto-approved LOW risk request %s (%s)",
                request.request_id,
                request.action_type,
            )
            return ApprovalStatus.APPROVED

        # Pick callback
        callback = self._callback or self._cli_approval_callback

        # Track as pending
        self._pending.append(request)

        try:
            status = self._invoke_with_timeout(callback, request)
        except _TimeoutError:
            status = ApprovalStatus.TIMEOUT
            logger.warning(
                "Approval timed out for request %s after %ds",
                request.request_id,
                request.timeout_seconds,
            )

        request.status = status

        # Remove from pending
        self._pending = [r for r in self._pending if r.request_id != request.request_id]

        self._log_decision(request, auto=False)
        return status

    def get_approval_log(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Return the approval log, optionally limited to the last *limit* entries."""
        if limit is not None:
            return self.approval_log[-limit:]
        return list(self.approval_log)

    @property
    def pending_count(self) -> int:
        """Number of requests currently awaiting a decision."""
        return len(self._pending)

    # -- built-in callbacks --------------------------------------------------

    @staticmethod
    def _cli_approval_callback(request: ApprovalRequest) -> ApprovalStatus:
        """Interactive CLI callback using rich console."""
        try:
            from rich.console import Console
            from rich.panel import Panel
            from rich.prompt import Confirm
            from rich.table import Table
        except ImportError:
            # Graceful fallback if rich is missing at runtime
            logger.error("rich is not installed; auto-denying request %s", request.request_id)
            return ApprovalStatus.DENIED

        console = Console()

        # Build a summary table
        table = Table(show_header=False, box=None, padding=(0, 2))
        table.add_column("Field", style="bold cyan")
        table.add_column("Value")
        table.add_row("Request ID", request.request_id)
        table.add_row("Agent", request.agent_id)
        table.add_row("Action", request.action_type)
        table.add_row("Resource", request.resource_type)
        table.add_row("Permission", request.permission_level)
        table.add_row("Risk Level", request.risk_level)
        table.add_row("Description", request.description)
        if request.metadata:
            for key, value in request.metadata.items():
                table.add_row(f"  {key}", str(value))

        risk_color = {
            "LOW": "green",
            "MEDIUM": "yellow",
            "HIGH": "red",
            "CRITICAL": "bold red",
        }.get(request.risk_level.upper(), "white")

        console.print()
        console.print(
            Panel(
                table,
                title=f"[bold]HITL Approval Required[/bold] [{risk_color}]({request.risk_level.upper()})[/{risk_color}]",
                border_style=risk_color,
            )
        )

        try:
            approved = Confirm.ask(
                "[bold]Approve this action?[/bold]",
                default=False,
                console=console,
            )
        except EOFError:
            # Non-interactive environment -- auto-deny
            logger.info("Non-interactive terminal detected; denying request %s", request.request_id)
            return ApprovalStatus.DENIED

        return ApprovalStatus.APPROVED if approved else ApprovalStatus.DENIED

    @staticmethod
    def _auto_approve_callback(request: ApprovalRequest) -> ApprovalStatus:
        """Auto-approve LOW risk, deny everything else."""
        if request.risk_level.upper() == "LOW":
            return ApprovalStatus.APPROVED
        return ApprovalStatus.DENIED

    # -- internal helpers ----------------------------------------------------

    def _invoke_with_timeout(
        self,
        callback: ApprovalCallback,
        request: ApprovalRequest,
    ) -> ApprovalStatus:
        """Call *callback* with a timeout.

        On platforms that support ``SIGALRM`` (Unix/macOS) the timeout is
        enforced via a signal handler.  On other platforms (Windows) the
        callback runs without a hard timeout -- the caller should set their
        own deadline inside the callback if needed.
        """
        timeout = request.timeout_seconds or self.default_timeout

        if not hasattr(signal, "SIGALRM"):
            # Windows -- just call directly, no signal-based timeout
            return callback(request)

        def _alarm_handler(signum: int, frame: Any) -> None:
            raise _TimeoutError()

        old_handler = signal.signal(signal.SIGALRM, _alarm_handler)
        signal.alarm(timeout)
        try:
            result = callback(request)
        except _TimeoutError:
            raise
        finally:
            signal.alarm(0)
            signal.signal(signal.SIGALRM, old_handler)

        return result

    def _log_decision(self, request: ApprovalRequest, *, auto: bool) -> None:
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "request_id": request.request_id,
            "agent_id": request.agent_id,
            "action_type": request.action_type,
            "resource_type": request.resource_type,
            "risk_level": request.risk_level,
            "status": request.status.value,
            "auto": auto,
            "description": request.description,
        }
        self.approval_log.append(entry)

        # Keep log bounded
        if len(self.approval_log) > 1000:
            self.approval_log = self.approval_log[-1000:]

        logger.info(
            "HITL decision: %s -> %s (auto=%s)",
            request.request_id,
            request.status.value,
            auto,
        )
