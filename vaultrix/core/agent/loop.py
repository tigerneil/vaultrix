"""ReAct agent loop with Anthropic tool-use integration.

Flow:  User goal -> LLM reasons -> picks tool -> we check permissions
-> execute tool -> feed result back -> repeat until done.

Includes anti-hallucination guards, cancellation support, and
loop-detection inspired by DeepAudit's verification patterns.
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

from vaultrix.core.permissions.manager import PermissionDeniedException, PermissionManager
from vaultrix.core.tools.base import Tool, ToolRegistry, ToolResult

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """\
You are Vaultrix, a secure autonomous AI agent.  You operate inside an
isolated sandbox with strict permissions.  Use the available tools to
accomplish the user's goal.

RULES:
- You MUST use tools to gather information before making claims.
- If a tool call is denied due to permissions, explain why and suggest alternatives.
- Never attempt to bypass security controls.
- Do not fabricate file paths, outputs, or data you have not observed through tool calls.
"""


@dataclass
class LoopStep:
    """One step in the agent loop (for history / streaming)."""

    role: str  # "assistant" | "tool"
    content: str = ""
    tool_name: Optional[str] = None
    tool_input: Optional[Dict[str, Any]] = None
    tool_result: Optional[str] = None
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


OnStepCallback = Callable[[LoopStep], None]


class AgentLoop:
    """Permission-aware ReAct loop powered by Anthropic tool-use.

    Includes anti-hallucination guards and resilience features inspired
    by DeepAudit's multi-agent patterns.

    Parameters
    ----------
    permission_manager:
        Checks tool permissions before execution.
    tool_registry:
        Available tools.
    model:
        Anthropic model name.
    max_steps:
        Hard cap on reasoning iterations.
    min_tool_calls:
        Minimum tool invocations required before the LLM can finish
        without a tool call (anti-hallucination guard).  Set to 0 to
        disable.
    max_repeated_failures:
        After this many consecutive identical tool failures, the loop
        injects a warning asking the LLM to change strategy.
    system_prompt:
        Optional override for the system prompt.
    on_step:
        Optional callback invoked after each step.
    """

    def __init__(
        self,
        permission_manager: PermissionManager,
        tool_registry: ToolRegistry,
        *,
        model: str = "claude-sonnet-4-20250514",
        max_steps: int = 20,
        min_tool_calls: int = 1,
        max_repeated_failures: int = 3,
        system_prompt: Optional[str] = None,
        on_step: Optional[OnStepCallback] = None,
    ) -> None:
        self.pm = permission_manager
        self.tools = tool_registry
        self.model = model
        self.max_steps = max_steps
        self.min_tool_calls = min_tool_calls
        self.max_repeated_failures = max_repeated_failures
        self.system_prompt = system_prompt or _SYSTEM_PROMPT
        self.on_step = on_step
        self.history: List[LoopStep] = []

        # Anti-hallucination tracking
        self._tool_call_count = 0
        self._failed_tool_calls: List[str] = []  # serialised (name, input) pairs
        self._consecutive_failures = 0

        # Cancellation support
        self._cancelled = threading.Event()

    @property
    def cancelled(self) -> bool:
        return self._cancelled.is_set()

    def cancel(self) -> None:
        """Request graceful cancellation of the loop."""
        self._cancelled.set()

    # ------------------------------------------------------------------

    def run(self, user_goal: str, *, api_key: Optional[str] = None) -> str:
        """Execute the agent loop and return the final assistant text."""
        try:
            import anthropic  # noqa: F401
        except ImportError:
            return self._dry_run(user_goal)

        if api_key is None:
            import os
            api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            return self._dry_run(user_goal)

        import anthropic as anth

        client = anth.Anthropic(api_key=api_key)
        messages: List[Dict[str, Any]] = [{"role": "user", "content": user_goal}]
        tool_defs = self.tools.to_anthropic_tools()

        for step_idx in range(self.max_steps):
            # Check cancellation before LLM call
            if self.cancelled:
                return "[cancelled]"

            try:
                response = client.messages.create(
                    model=self.model,
                    max_tokens=4096,
                    system=self.system_prompt,
                    tools=tool_defs,
                    messages=messages,
                )
            except Exception as exc:
                logger.error("LLM call failed at step %d: %s", step_idx, exc)
                return f"[LLM error: {exc}]"

            # Collect assistant text and tool_use blocks
            assistant_text_parts: List[str] = []
            tool_uses: List[Dict[str, Any]] = []

            for block in response.content:
                if block.type == "text":
                    assistant_text_parts.append(block.text)
                elif block.type == "tool_use":
                    tool_uses.append({
                        "id": block.id,
                        "name": block.name,
                        "input": block.input,
                    })

            full_text = "\n".join(assistant_text_parts)
            self._emit(LoopStep(role="assistant", content=full_text))

            # Anti-hallucination: if the LLM tries to finish without
            # enough tool calls, push it to use tools first.
            if not tool_uses or response.stop_reason == "end_turn":
                if self._tool_call_count < self.min_tool_calls:
                    logger.info(
                        "Anti-hallucination: only %d/%d tool calls, "
                        "requesting more evidence",
                        self._tool_call_count,
                        self.min_tool_calls,
                    )
                    messages.append({"role": "assistant", "content": response.content})
                    messages.append({
                        "role": "user",
                        "content": (
                            "You have not used enough tools to support your answer. "
                            "Please use at least one tool to gather evidence before "
                            "giving your final response."
                        ),
                    })
                    continue
                return full_text

            # Add the raw assistant response to messages
            messages.append({"role": "assistant", "content": response.content})

            # Execute each tool call
            tool_results_content: List[Dict[str, Any]] = []
            for tu in tool_uses:
                if self.cancelled:
                    return "[cancelled]"

                result = self._invoke_tool(tu["name"], tu["input"])
                self._emit(LoopStep(
                    role="tool",
                    tool_name=tu["name"],
                    tool_input=tu["input"],
                    tool_result=result.output or result.error,
                ))
                tool_results_content.append({
                    "type": "tool_result",
                    "tool_use_id": tu["id"],
                    "content": result.output if result.success else f"ERROR: {result.error}",
                })

                # Track for anti-hallucination / loop detection
                self._tool_call_count += 1
                self._track_failure(tu["name"], tu["input"], result)

            # Loop detection: inject warning after repeated failures
            if self._consecutive_failures >= self.max_repeated_failures:
                tool_results_content.append({
                    "type": "tool_result",
                    "tool_use_id": tool_uses[-1]["id"],
                    "content": (
                        "WARNING: You have had multiple consecutive tool failures. "
                        "Please change your approach or try a different tool."
                    ),
                })
                self._consecutive_failures = 0

            messages.append({"role": "user", "content": tool_results_content})

        return "[max steps reached]"

    # ------------------------------------------------------------------

    def _invoke_tool(self, name: str, inputs: Dict[str, Any]) -> ToolResult:
        tool = self.tools.get(name)
        if tool is None:
            return ToolResult(success=False, error=f"Unknown tool: {name}")

        # Permission gate
        for resource, level in tool.required_permissions:
            path = inputs.get("path")
            if not self.pm.check_permission(resource, level, path=path):
                return ToolResult(
                    success=False,
                    error=f"Permission denied: {resource.value}:{level.value}",
                )

        try:
            return tool.execute(**inputs)
        except Exception as exc:
            logger.exception("Tool %s raised", name)
            return ToolResult(success=False, error=str(exc))

    def _track_failure(
        self, name: str, inputs: Dict[str, Any], result: ToolResult
    ) -> None:
        """Track consecutive failures for loop detection."""
        if result.success:
            self._consecutive_failures = 0
            return
        call_sig = f"{name}:{sorted(inputs.items())}"
        if self._failed_tool_calls and self._failed_tool_calls[-1] == call_sig:
            self._consecutive_failures += 1
        else:
            self._consecutive_failures = 1
        self._failed_tool_calls.append(call_sig)
        # Keep bounded
        if len(self._failed_tool_calls) > 100:
            self._failed_tool_calls = self._failed_tool_calls[-50:]

    def _dry_run(self, user_goal: str) -> str:
        """Summarise tools when no LLM is available."""
        lines = [
            "Dry-run mode (no Anthropic API key or SDK).",
            f"Goal: {user_goal}",
            "",
            "Available tools:",
        ]
        for t in self.tools.all_tools():
            perms = ", ".join(f"{r.value}:{l.value}" for r, l in t.required_permissions) or "none"
            lines.append(f"  - {t.name}: {t.description}  [perms: {perms}]")
        text = "\n".join(lines)
        self._emit(LoopStep(role="assistant", content=text))
        return text

    def _emit(self, step: LoopStep) -> None:
        self.history.append(step)
        if self.on_step:
            self.on_step(step)
